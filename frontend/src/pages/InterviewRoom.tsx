import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getCurrentQuestion, submitAnswer, pauseInterview,
  resumeInterview, endInterview, getSession, getQuestionAudioUrl,
  type QuestionResponse, type SessionState,
} from '../api/client'
import {
  Mic, MicOff, Video, VideoOff, Phone, Pause, Play,
  Send, SkipForward, Loader2, BrainCircuit,
  ChevronRight, MessageSquare, AlertCircle,
  X, Clock, CheckCircle2, Volume2, VolumeX
} from 'lucide-react'
import clsx from 'clsx'

/* ─── Web Speech API type stubs ─────────────────────────────────────────── */
interface SpeechRecognition extends EventTarget {
  continuous: boolean; interimResults: boolean; lang: string
  start(): void; stop(): void; abort(): void
  onresult: ((e: SpeechRecognitionEvent) => void) | null
  onerror: ((e: Event) => void) | null; onend: (() => void) | null
}
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList
}
declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition
    webkitSpeechRecognition: new () => SpeechRecognition
  }
}

/* ─── AI Avatar with speaking animation ─────────────────────────────────── */
function AIAvatar({ speaking }: { speaking: boolean }) {
  return (
    <div className="relative flex flex-col items-center">
      {/* Outer glow ring */}
      <div className={clsx(
        'absolute inset-0 rounded-full transition-all duration-700',
        speaking ? 'animate-glow' : ''
      )} />
      {/* Avatar circle */}
      <div className={clsx(
        'w-28 h-28 rounded-full flex items-center justify-center relative',
        'bg-gradient-to-br from-brand-600 via-purple-700 to-pink-700',
        'shadow-2xl shadow-brand-900/60',
        speaking ? 'ring-4 ring-brand-400/60 ring-offset-4 ring-offset-surface-800' : 'ring-2 ring-brand-700/40 ring-offset-2 ring-offset-surface-800'
      )}>
        <BrainCircuit size={48} className="text-white" />
      </div>

      {/* Speaking waveform bars */}
      {speaking && (
        <div className="flex items-end gap-1 mt-3 h-6">
          {[1, 1.6, 0.8, 1.4, 1, 0.6, 1.3].map((h, i) => (
            <div key={i} className="speaking-bar"
              style={{ height: `${h * 14}px`, animationDelay: `${i * 0.1}s` }} />
          ))}
        </div>
      )}
      {!speaking && <div className="h-6 mt-3" />}

      <p className="text-sm font-semibold text-slate-300 mt-2">AI Interviewer</p>
      <p className="text-xs text-brand-400">{speaking ? 'Speaking…' : 'Listening'}</p>
    </div>
  )
}


/* ─── Main Interview Room ────────────────────────────────────────────────── */
export default function InterviewRoom() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()

  // Session state
  const [session, setSession] = useState<SessionState | null>(null)
  const [question, setQuestion] = useState<QuestionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionStatus, setSessionStatus] = useState<string>('active')

  // Answer
  const [answerText, setAnswerText] = useState('')
  const [lastEval, setLastEval] = useState<{
    overall_score: number; feedback: string;
    concepts_demonstrated: string[]; missing_concepts: string[]
  } | null>(null)

  // Camera & mic
  const videoRef = useRef<HTMLVideoElement>(null)
  const [cameraOn, setCameraOn] = useState(false)
  const [micOn, setMicOn] = useState(false)
  const streamRef = useRef<MediaStream | null>(null)

  // Speech recognition
  const recognizerRef = useRef<SpeechRecognition | null>(null)
  const [transcribing, setTranscribing] = useState(false)

  // TTS / AI speaking
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [aiSpeaking, setAiSpeaking] = useState(false)
  const [ttsEnabled, setTtsEnabled] = useState(true)


  // Timer
  const [elapsedSec, setElapsedSec] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Transcript log
  const [transcript, setTranscript] = useState<
    { role: 'ai' | 'you'; text: string; score?: number }[]
  >([])
  const transcriptRef = useRef<HTMLDivElement>(null)

  // ── Load initial state ───────────────────────────────────────────────────
  useEffect(() => {
    if (!sessionId) return
    Promise.all([getSession(sessionId), getCurrentQuestion(sessionId)])
      .then(([{ data: s }, { data: q }]) => {
        setSession(s); setQuestion(q); setSessionStatus(s.status)
        if (s.status === 'completed') navigate(`/results/${sessionId}`)
      })
      .catch(e => setError(e.message ?? 'Failed to load session'))
      .finally(() => setLoading(false))
  }, [sessionId])

  // ── Auto-play question audio when question changes ────────────────────────
  useEffect(() => {
    if (!question || !sessionId || !ttsEnabled) return
    setAiSpeaking(false)
    setTranscript(prev => [...prev, { role: 'ai', text: question.question_text }])

    const audioUrl = getQuestionAudioUrl(sessionId)
    const audio = new Audio(audioUrl)
    audioRef.current = audio
    audio.onplay = () => setAiSpeaking(true)
    audio.onended = () => setAiSpeaking(false)
    audio.onerror = () => setAiSpeaking(false) // TTS not configured — silent fallback
    audio.play().catch(() => setAiSpeaking(false))

    return () => { audio.pause(); audio.src = '' }
  }, [question?.id, ttsEnabled])

  // ── Timer ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (sessionStatus !== 'active') return
    timerRef.current = setInterval(() => setElapsedSec(s => s + 1), 1000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [sessionStatus])

  // ── Transcript scroll ────────────────────────────────────────────────────
  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: 'smooth' })
  }, [transcript])

  // ── Camera ───────────────────────────────────────────────────────────────
  const toggleCamera = async () => {
    if (cameraOn) {
      streamRef.current?.getVideoTracks().forEach(t => t.stop())
      if (videoRef.current) videoRef.current.srcObject = null
      setCameraOn(false)
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        streamRef.current = stream
        if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play() }
        setCameraOn(true)
      } catch { setError('Camera access denied.') }
    }
  }

  // ── Microphone / STT ─────────────────────────────────────────────────────
  const toggleMic = useCallback(() => {
    const SR = window.SpeechRecognition ?? window.webkitSpeechRecognition
    if (!SR) { setError('Speech recognition not supported in this browser.'); return }

    if (micOn) {
      recognizerRef.current?.stop(); setMicOn(false); setTranscribing(false)
    } else {
      const r = new SR()
      r.continuous = true; r.interimResults = true; r.lang = 'en-US'
      r.onresult = (e: SpeechRecognitionEvent) => {
        let interim = ''; let final = ''
        for (let i = e.results.length - 1; i >= 0; i--) {
          if (e.results[i].isFinal) { final += e.results[i][0].transcript }
          else { interim += e.results[i][0].transcript }
        }
        setAnswerText(prev => (final ? prev + ' ' + final : prev + interim).trim())
      }
      r.onerror = () => { setMicOn(false); setTranscribing(false) }
      r.onend = () => { setTranscribing(false) }
      r.start()
      recognizerRef.current = r; setMicOn(true); setTranscribing(true)
    }
  }, [micOn])

  // ── Submit answer ─────────────────────────────────────────────────────────
  const handleSubmit = async (skip = false) => {
    if (!sessionId || submitting) return
    recognizerRef.current?.stop(); setMicOn(false); setTranscribing(false)

    const text = skip ? null : answerText.trim() || null
    if (!skip && !text) { setError('Please type or speak your answer before submitting.'); return }

    setSubmitting(true); setError(null)
    try {
      const { data } = await submitAnswer(sessionId, text, skip)

      if (!skip && text) setTranscript(prev => [...prev, { role: 'you', text }])
      if (data.evaluation) {
        setLastEval(data.evaluation)
        setTranscript(prev => prev.map((t, i) =>
          i === prev.length - 1 && t.role === 'you'
            ? { ...t, score: data.evaluation!.overall_score }
            : t))
      }

      setAnswerText('')

      if (data.next_action === 'end_interview' || data.message.includes('complete')) {
        navigate(`/results/${sessionId}`)
        return
      }

      // Load next question
      const { data: nextQ } = await getCurrentQuestion(sessionId)
      setQuestion(nextQ)
      setLastEval(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to submit answer')
    } finally { setSubmitting(false) }
  }

  // ── Pause / Resume ───────────────────────────────────────────────────────
  const handlePause = async () => {
    if (!sessionId) return
    if (sessionStatus === 'paused') {
      await resumeInterview(sessionId); setSessionStatus('active')
    } else {
      await pauseInterview(sessionId); setSessionStatus('paused')
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }

  // ── End interview ─────────────────────────────────────────────────────────
  const handleEnd = async () => {
    if (!sessionId || !confirm('End this interview now and go to results?')) return
    await endInterview(sessionId)
    navigate(`/results/${sessionId}`)
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  const progress = question ? question.session_progress : null
  const pct = progress ? progress.percent : 0

  /* ════════════════════════════════════════════════════════════════════════
     RENDER
  ════════════════════════════════════════════════════════════════════════ */
  if (loading) return (
    <div className="flex items-center justify-center h-screen bg-surface-900">
      <Loader2 size={40} className="animate-spin text-brand-400" />
    </div>
  )

  return (
    <div className="flex flex-col h-screen bg-surface-900 overflow-hidden font-sans">

      {/* ── Top bar ──────────────────────────────────────────────────────── */}
      <header className="glass-strong border-b border-white/5 px-6 py-3 flex items-center gap-4 z-10 flex-shrink-0">
        {/* Brand */}
        <div className="flex items-center gap-2 mr-4">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center">
            <BrainCircuit size={14} className="text-white" />
          </div>
          <span className="font-bold text-slate-200 text-sm">AI Interview</span>
        </div>

        {/* Progress bar */}
        <div className="flex-1 max-w-xs">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span>Question {progress?.current ?? 0} of {progress?.total ?? 0}</span>
            <span>{pct}%</span>
          </div>
          <div className="score-bar h-1.5">
            <div className="h-full rounded-full bg-brand-500 transition-all duration-500"
              style={{ width: `${pct}%` }} />
          </div>
        </div>

        {/* Competency */}
        {question && (
          <div className="hidden md:flex items-center gap-2 ml-2">
            <span className="badge badge-purple text-xs">{question.competency}</span>
            <span className={clsx('badge text-xs',
              question.difficulty === 'hard' ? 'badge-red'
              : question.difficulty === 'medium' ? 'badge-yellow' : 'badge-green')}>
              {question.difficulty}
            </span>
            {question.is_follow_up && <span className="badge badge-gray text-xs">Follow-up</span>}

          </div>
        )}

        {/* Timer */}
        <div className="flex items-center gap-1.5 ml-auto">
          <Clock size={13} className="text-slate-500" />
          <span className="font-mono text-slate-300 text-sm">{fmt(elapsedSec)}</span>
        </div>

        {/* TTS toggle */}
        <button onClick={() => setTtsEnabled(v => !v)}
          className={clsx('p-2 rounded-lg transition-colors',
            ttsEnabled ? 'text-brand-400 hover:bg-brand-900/30' : 'text-slate-600 hover:bg-surface-700')}
          title={ttsEnabled ? 'Mute AI voice' : 'Enable AI voice'}>
          {ttsEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
        </button>
      </header>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Left: Video area ─────────────────────────────────────────── */}
        <div className="flex flex-col w-80 flex-shrink-0 border-r border-white/5 glass-strong">
          {/* AI Interviewer panel */}
          <div className="flex-1 flex flex-col items-center justify-center p-6 bg-gradient-to-b from-surface-800 to-surface-900">
            <AIAvatar speaking={aiSpeaking} />

            {/* Paused overlay */}
            {sessionStatus === 'paused' && (
              <div className="mt-6 flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
                <Pause size={14} /> Interview Paused
              </div>
            )}
          </div>

          {/* User camera (small PiP) */}
          <div className="relative mx-4 mb-4">
            <div className={clsx(
              'w-full aspect-video rounded-xl overflow-hidden bg-surface-700 flex items-center justify-center',
              'border border-white/5',
            )}>
              {cameraOn
                ? <video ref={videoRef} autoPlay muted playsInline
                    className="w-full h-full object-cover scale-x-[-1]" />
                : <div className="flex flex-col items-center gap-2 text-slate-600">
                    <VideoOff size={24} />
                    <span className="text-xs">Camera off</span>
                  </div>}
            </div>
            <div className="absolute bottom-2 right-2">
              <span className="badge badge-gray text-xs">You</span>
            </div>
          </div>

          {/* Camera / Mic controls */}
          <div className="flex items-center justify-center gap-3 pb-4 px-4">
            <button onClick={toggleCamera}
              className={clsx('w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200',
                cameraOn ? 'bg-surface-600 text-slate-200 hover:bg-surface-500'
                : 'bg-red-900/40 text-red-400 hover:bg-red-900/60')}>
              {cameraOn ? <Video size={16} /> : <VideoOff size={16} />}
            </button>
            <button onClick={toggleMic}
              className={clsx('w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200',
                micOn ? 'bg-brand-600 text-white ring-2 ring-brand-400 ring-offset-1 ring-offset-surface-800 animate-pulse-slow'
                : 'bg-surface-600 text-slate-200 hover:bg-surface-500')}>
              {micOn ? <Mic size={16} /> : <MicOff size={16} />}
            </button>
            <button onClick={handlePause}
              className="w-10 h-10 rounded-full bg-surface-600 text-slate-200 hover:bg-surface-500 flex items-center justify-center transition-all">
              {sessionStatus === 'paused' ? <Play size={16} /> : <Pause size={16} />}
            </button>
            <button onClick={handleEnd}
              className="w-10 h-10 rounded-full bg-red-900/40 text-red-400 hover:bg-red-900/70 flex items-center justify-center transition-all">
              <Phone size={16} />
            </button>
          </div>
        </div>

        {/* ── Center: Question + Answer ────────────────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Question card */}
          {question && (
            <div className="px-6 pt-6 pb-4 flex-shrink-0">
              <div className="glass rounded-2xl p-6 border border-brand-600/20">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-xl bg-brand-600/20 flex-shrink-0">
                    <BrainCircuit size={18} className="text-brand-400" />
                  </div>
                  <div className="flex-1">
                    <p className="text-xs text-brand-400 font-medium mb-2">
                      {question.question_type.replace(/_/g, ' ').toUpperCase()}
                      {question.is_follow_up ? ' • FOLLOW-UP' : ''}
                      {' '}• {question.time_allocation_minutes} min
                    </p>
                    <p className="text-slate-100 text-lg leading-relaxed font-medium">
                      {question.question_text}
                    </p>
                    {question.requires_whiteboard && (
                      <button onClick={() => setShowWhiteboard(true)}
                        className="mt-3 btn-secondary text-xs gap-1.5 py-1.5">
                        <PenTool size={12} /> Open Whiteboard for Diagram
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Last eval flash */}
          {lastEval && (
            <div className="px-6 pb-2 flex-shrink-0 animate-slide-up">
              <div className="glass rounded-xl p-3 border border-emerald-500/20 flex items-start gap-3">
                <CheckCircle2 size={15} className="text-emerald-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-emerald-400 font-medium mb-0.5">
                    Answer recorded — Score: {lastEval.overall_score.toFixed(1)}/4
                  </p>
                  <p className="text-xs text-slate-400 line-clamp-2">{lastEval.feedback}</p>
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="px-6 pb-2 flex-shrink-0">
              <div className="flex items-center gap-2 p-3 rounded-xl bg-red-900/20 border border-red-500/30 text-red-300 text-xs">
                <AlertCircle size={13} /> {error}
                <button onClick={() => setError(null)} className="ml-auto"><X size={12} /></button>
              </div>
            </div>
          )}

          {/* Answer area */}
          <div className="flex-1 flex flex-col px-6 pb-6 min-h-0">
            <div className="flex items-center gap-2 mb-2 flex-shrink-0">
              <MessageSquare size={13} className="text-slate-500" />
              <span className="text-xs text-slate-500">Your answer</span>
              {micOn && (
                <span className="flex items-center gap-1 text-xs text-brand-400 animate-pulse">
                  <Mic size={10} /> Recording…
                </span>
              )}
            </div>
            <textarea
              className="textarea flex-1 resize-none text-sm leading-relaxed"
              placeholder={micOn
                ? 'Speaking… your words appear here automatically'
                : 'Type your answer here, or click the mic to speak…'}
              value={answerText}
              onChange={e => setAnswerText(e.target.value)}
              disabled={sessionStatus === 'paused' || submitting}
            />
            <div className="flex items-center gap-3 mt-3 flex-shrink-0">
              <button
                onClick={() => handleSubmit(true)}
                disabled={submitting || sessionStatus === 'paused'}
                className="btn-secondary gap-1.5 text-sm">
                <SkipForward size={14} /> Skip
              </button>
              <button
                onClick={() => handleSubmit(false)}
                disabled={submitting || sessionStatus === 'paused'}
                className="btn-primary flex-1 justify-center">
                {submitting
                  ? <><Loader2 size={14} className="animate-spin" /> Evaluating…</>
                  : <><Send size={14} /> Submit Answer <ChevronRight size={14} /></>}
              </button>
            </div>
          </div>
        </div>

        {/* ── Right: Transcript sidebar ─────────────────────────────────── */}
        <div className="w-72 flex-shrink-0 border-l border-white/5 glass-strong flex flex-col">
          <div className="px-4 pt-4 pb-2 border-b border-white/5 flex-shrink-0">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Transcript</p>
          </div>
          <div ref={transcriptRef} className="flex-1 overflow-y-auto p-4 space-y-3">
            {transcript.length === 0 && (
              <p className="text-xs text-slate-600 text-center mt-4">Interview transcript will appear here</p>
            )}
            {transcript.map((entry, i) => (
              <div key={i} className={clsx('text-xs rounded-xl p-3',
                entry.role === 'ai'
                  ? 'bg-brand-900/30 border border-brand-800/40'
                  : 'bg-surface-700/60 border border-white/5')}>
                <p className={clsx('font-semibold mb-1 text-xs',
                  entry.role === 'ai' ? 'text-brand-400' : 'text-slate-400')}>
                  {entry.role === 'ai' ? '🤖 Interviewer' : '🧑 You'}
                  {entry.score != null && (
                    <span className="ml-2 text-emerald-400 font-mono">{entry.score.toFixed(1)}/4</span>
                  )}
                </p>
                <p className="text-slate-300 leading-relaxed">{entry.text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
