import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadResume, analyzeJD, createMatch, createInterview } from '../api/client'
import {
  Upload, FileText, Briefcase, Settings2, ChevronRight,
  Loader2, CheckCircle2, AlertCircle, X, Zap
} from 'lucide-react'
import clsx from 'clsx'

type Step = 'upload' | 'jd' | 'config' | 'starting'

interface Config {
  mode: string; difficulty: string; duration_minutes: number
  max_questions: number; candidate_name: string
}

const STEPS = [
  { key: 'upload' as Step, label: 'Resume',    icon: Upload },
  { key: 'jd'     as Step, label: 'Job Description', icon: Briefcase },
  { key: 'config' as Step, label: 'Configure', icon: Settings2 },
]

export default function NewInterview() {
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('upload')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Step data
  const [resumeId, setResumeId] = useState<string | null>(null)
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [jdId, setJdId] = useState<string | null>(null)
  const [jdText, setJdText] = useState('')
  const [matchId, setMatchId] = useState<string | null>(null)
  const [config, setConfig] = useState<Config>({
    mode: 'mixed', difficulty: 'medium',
    duration_minutes: 30, max_questions: 10, candidate_name: '',
  })

  const [dragOver, setDragOver] = useState(false)

  // ── Step 1: Upload resume ──────────────────────────────────────────────────
  const handleFile = useCallback(async (file: File) => {
    if (!file.name.match(/\.(pdf|docx)$/i)) {
      setError('Only PDF and DOCX files are accepted.'); return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('File too large (max 10 MB).'); return
    }
    setError(null); setLoading(true); setResumeFile(file)
    try {
      const { data } = await uploadResume(file)
      if (data.extraction_status === 'failed')
        throw new Error('Resume extraction failed — try a different file format.')
      setResumeId(data.id)
      setStep('jd')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Upload failed'
      setError(msg); setResumeFile(null)
    } finally { setLoading(false) }
  }, [])

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  // ── Step 2: Analyze JD ────────────────────────────────────────────────────
  const handleJD = async () => {
    if (jdText.trim().length < 50) {
      setError('Please paste a job description (at least 50 characters).'); return
    }
    setError(null); setLoading(true)
    try {
      const { data } = await analyzeJD(jdText)
      setJdId(data.id)
      // Also run matching
      if (resumeId) {
        const { data: match } = await createMatch(resumeId, data.id)
        setMatchId(match.id)
      }
      setStep('config')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'JD analysis failed')
    } finally { setLoading(false) }
  }

  // ── Step 3: Start interview ───────────────────────────────────────────────
  const handleStart = async () => {
    if (!resumeId || !jdId) return
    setError(null); setStep('starting'); setLoading(true)
    try {
      const { data: session } = await createInterview({
        resume_id: resumeId, jd_id: jdId,
        match_report_id: matchId ?? undefined,
        candidate_name: config.candidate_name || undefined,
        mode: config.mode, difficulty: config.difficulty,
        duration_minutes: config.duration_minutes,
        max_questions: config.max_questions,
      })
      navigate(`/interview/${session.id}`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start interview')
      setStep('config')
    } finally { setLoading(false) }
  }

  const stepIndex = STEPS.findIndex(s => s.key === step)

  return (
    <div className="p-8 max-w-2xl mx-auto animate-fade-in">
      <h1 className="text-3xl font-bold gradient-text mb-1">New Interview</h1>
      <p className="text-slate-400 text-sm mb-8">Set up your personalized AI-driven practice interview</p>

      {/* Step indicator */}
      <div className="flex items-center gap-3 mb-10">
        {STEPS.map((s, i) => {
          const done = i < stepIndex
          const active = i === stepIndex
          const Icon = s.icon
          return (
            <div key={s.key} className="flex items-center gap-2">
              <div className={clsx('flex items-center gap-2 px-3 py-1.5 rounded-xl text-sm font-medium transition-all',
                active ? 'bg-brand-600/20 text-brand-300 border border-brand-500/40'
                : done ? 'bg-emerald-600/20 text-emerald-400'
                : 'text-slate-600')}>
                {done ? <CheckCircle2 size={14} /> : <Icon size={14} />}
                {s.label}
              </div>
              {i < STEPS.length - 1 && <ChevronRight size={14} className="text-slate-700" />}
            </div>
          )
        })}
      </div>

      {error && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-red-900/20 border border-red-500/30 text-red-300 text-sm mb-6">
          <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto"><X size={14} /></button>
        </div>
      )}

      {/* ── Step: Upload ─────────────────────────────────────────────────── */}
      {step === 'upload' && (
        <div className="glass rounded-2xl p-8 animate-slide-up">
          <h2 className="text-lg font-semibold text-slate-200 mb-2 flex items-center gap-2">
            <Upload size={18} className="text-brand-400" /> Upload Your Resume
          </h2>
          <p className="text-slate-400 text-sm mb-6">PDF or DOCX • Max 10 MB</p>

          <label
            className={clsx(
              'flex flex-col items-center justify-center h-48 rounded-xl border-2 border-dashed cursor-pointer transition-all duration-200',
              dragOver ? 'border-brand-400 bg-brand-900/20' : 'border-surface-500 hover:border-brand-600/50 hover:bg-surface-700/30',
              loading && 'opacity-50 pointer-events-none'
            )}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}>
            <input type="file" accept=".pdf,.docx" className="hidden"
              onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
            {loading ? (
              <div className="flex flex-col items-center gap-3">
                <Loader2 size={32} className="animate-spin text-brand-400" />
                <p className="text-slate-400 text-sm">Parsing resume with AI…</p>
              </div>
            ) : resumeFile ? (
              <div className="flex flex-col items-center gap-2">
                <CheckCircle2 size={32} className="text-emerald-400" />
                <p className="text-slate-300 font-medium">{resumeFile.name}</p>
                <p className="text-slate-500 text-xs">Click to replace</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className="p-4 rounded-xl bg-surface-700">
                  <FileText size={28} className="text-brand-400" />
                </div>
                <p className="text-slate-300 font-medium">Drag & drop or click to upload</p>
                <p className="text-slate-500 text-xs">PDF or DOCX</p>
              </div>
            )}
          </label>
        </div>
      )}

      {/* ── Step: JD ─────────────────────────────────────────────────────── */}
      {step === 'jd' && (
        <div className="glass rounded-2xl p-8 animate-slide-up">
          <h2 className="text-lg font-semibold text-slate-200 mb-2 flex items-center gap-2">
            <Briefcase size={18} className="text-brand-400" /> Paste Job Description
          </h2>
          <p className="text-slate-400 text-sm mb-4">
            Copy the full JD from the job posting. The AI will extract requirements and match them to your resume.
          </p>
          <textarea
            className="textarea h-64 mb-5 font-mono text-xs"
            placeholder="Paste the full job description here…"
            value={jdText}
            onChange={e => setJdText(e.target.value)}
          />
          <div className="flex gap-3">
            <button onClick={() => setStep('upload')} className="btn-secondary">Back</button>
            <button onClick={handleJD} disabled={loading} className="btn-primary flex-1">
              {loading ? <><Loader2 size={15} className="animate-spin" /> Analyzing JD…</> : <>Analyze & Match <ChevronRight size={15} /></>}
            </button>
          </div>
        </div>
      )}

      {/* ── Step: Config ─────────────────────────────────────────────────── */}
      {step === 'config' && (
        <div className="glass rounded-2xl p-8 animate-slide-up">
          <h2 className="text-lg font-semibold text-slate-200 mb-1 flex items-center gap-2">
            <Settings2 size={18} className="text-brand-400" /> Configure Interview
          </h2>
          <p className="text-slate-400 text-sm mb-6">Customise your session before starting.</p>

          <div className="space-y-5">
            <div>
              <label className="text-sm text-slate-400 mb-1.5 block">Your Name (optional)</label>
              <input type="text" className="input" placeholder="e.g. Alex Johnson"
                value={config.candidate_name}
                onChange={e => setConfig(c => ({ ...c, candidate_name: e.target.value }))} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-slate-400 mb-1.5 block">Mode</label>
                <select className="input" value={config.mode}
                  onChange={e => setConfig(c => ({ ...c, mode: e.target.value }))}>
                  <option value="mixed">Mixed (recommended)</option>
                  <option value="technical">Technical only</option>
                  <option value="behavioral">Behavioral only</option>
                  <option value="project-focused">Project-focused</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-slate-400 mb-1.5 block">Difficulty</label>
                <select className="input" value={config.difficulty}
                  onChange={e => setConfig(c => ({ ...c, difficulty: e.target.value }))}>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium (recommended)</option>
                  <option value="hard">Hard</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-slate-400 mb-1.5 block">Duration (minutes)</label>
                <select className="input" value={config.duration_minutes}
                  onChange={e => setConfig(c => ({ ...c, duration_minutes: Number(e.target.value) }))}>
                  {[15, 20, 30, 45, 60].map(v => <option key={v} value={v}>{v} min</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm text-slate-400 mb-1.5 block">Questions</label>
                <select className="input" value={config.max_questions}
                  onChange={e => setConfig(c => ({ ...c, max_questions: Number(e.target.value) }))}>
                  {[5, 8, 10, 12, 15, 20].map(v => <option key={v} value={v}>{v} questions</option>)}
                </select>
              </div>
            </div>

            {/* Match summary chip */}
            {matchId && (
              <div className="glass rounded-xl p-3 flex items-center gap-2 text-xs text-slate-400">
                <CheckCircle2 size={14} className="text-emerald-400 flex-shrink-0" />
                Match analysis complete. View it after the interview.
              </div>
            )}
          </div>

          <div className="flex gap-3 mt-6">
            <button onClick={() => setStep('jd')} className="btn-secondary">Back</button>
            <button onClick={handleStart} disabled={loading} className="btn-primary flex-1">
              <Zap size={15} /> Start Interview
            </button>
          </div>
        </div>
      )}

      {/* ── Starting ─────────────────────────────────────────────────────── */}
      {step === 'starting' && (
        <div className="glass rounded-2xl p-12 text-center animate-slide-up">
          <Loader2 size={40} className="animate-spin text-brand-400 mx-auto mb-4" />
          <p className="text-slate-200 font-semibold mb-1">Generating your interview plan…</p>
          <p className="text-slate-400 text-sm">AI is tailoring questions to your resume and the job description</p>
        </div>
      )}
    </div>
  )
}
