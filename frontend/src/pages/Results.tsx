import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getReport, getSession, type FinalReport as FinalReportType } from '../api/client'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'
import {
  CheckCircle2, XCircle, BookOpen, TrendingUp, Award,
  AlertTriangle, Loader2, ChevronLeft, Info, Download, BrainCircuit
} from 'lucide-react'

function ScoreGauge({ score }: { score: number }) {
  const pct = Math.round(score / 4 * 100)
  const r = 60; const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ
  const color = pct >= 70 ? '#10b981' : pct >= 45 ? '#f59e0b' : '#ef4444'
  const label = pct >= 70 ? 'Strong' : pct >= 45 ? 'Developing' : 'Needs Work'

  return (
    <div className="flex flex-col items-center">
      <svg width="160" height="160" viewBox="0 0 160 160">
        <circle cx="80" cy="80" r={r} fill="none" stroke="#1e1e35" strokeWidth="10" />
        <circle cx="80" cy="80" r={r} fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round"
          transform="rotate(-90 80 80)" style={{ transition: 'stroke-dasharray 1s ease' }} />
        <text x="80" y="75" textAnchor="middle" fill="white" fontSize="28" fontWeight="800">{pct}%</text>
        <text x="80" y="97" textAnchor="middle" fill={color} fontSize="13" fontWeight="600">{label}</text>
        <text x="80" y="114" textAnchor="middle" fill="#64748b" fontSize="11">Overall Score</text>
      </svg>
    </div>
  )
}

const CUSTOM_TOOLTIP = ({ active, payload, label }: Record<string, unknown>) => {
  if (!(active as boolean) || !(payload as unknown[])?.length) return null
  const data = (payload as Array<{ value: number }>)[0]
  return (
    <div className="glass rounded-xl p-3 text-xs border border-brand-600/30">
      <p className="text-slate-300 font-medium mb-1">{label as string}</p>
      <p className="text-brand-300 font-bold">{((data.value / 4) * 100).toFixed(0)}% ({data.value.toFixed(2)}/4)</p>
    </div>
  )
}

export default function Results() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [report, setReport] = useState<FinalReportType | null>(null)
  const [loading, setLoading] = useState(true)
  const [retrying, setRetrying] = useState(false)

  useEffect(() => { load() }, [sessionId])

  async function load() {
    if (!sessionId) return
    setLoading(true)
    try {
      const { data } = await getReport(sessionId)
      setReport(data)
    } catch {
      // Session might still be ending — try once more
      setRetrying(true)
      setTimeout(async () => {
        try { const { data } = await getReport(sessionId); setReport(data) }
        catch {}
        setRetrying(false); setLoading(false)
      }, 2000)
      return
    }
    setLoading(false)
  }

  if (loading || retrying) return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <Loader2 size={36} className="animate-spin text-brand-400" />
      <p className="text-slate-400 text-sm">{retrying ? 'Finalising report…' : 'Loading report…'}</p>
    </div>
  )

  if (!report) return (
    <div className="p-8">
      <p className="text-slate-400">Report not found.</p>
      <button onClick={() => navigate('/')} className="btn-secondary mt-4">← Dashboard</button>
    </div>
  )

  // Prepare chart data
  const competencyData = Object.entries(report.competency_scores ?? {}).map(([name, val]) => ({
    competency: name.length > 18 ? name.slice(0, 16) + '…' : name,
    score: val.average_score,
    fullName: name,
    questions: val.num_questions,
  }))

  const radarData = competencyData.slice(0, 8).map(d => ({
    subject: d.competency, value: (d.score / 4) * 100, fullMark: 100,
  }))

  const evaluations = (report.full_report as Record<string, unknown>)?.evaluations as Array<{
    question_text: string; overall_score: number; evaluator_feedback: string;
    skipped: boolean; competency: string; answer_text: string;
  }> ?? []

  return (
    <div className="p-8 max-w-5xl animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold gradient-text mb-1">Interview Report</h1>
          <p className="text-slate-400 text-sm">{new Date(report.created_at).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => navigate('/')} className="btn-secondary gap-1.5">
            <ChevronLeft size={14} /> Dashboard
          </button>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-900/20 border border-amber-500/20 text-xs text-amber-300 mb-8">
        <Info size={13} className="flex-shrink-0 mt-0.5" />
        {report.full_report?.disclaimer as string ?? 'This is an AI practice tool, not a validated hiring assessment.'}
      </div>

      {/* Score + Summary */}
      <div className="grid grid-cols-3 gap-5 mb-8">
        <div className="glass rounded-2xl p-6 flex items-center justify-center">
          <ScoreGauge score={report.overall_score ?? 0} />
        </div>
        <div className="glass rounded-2xl p-6 col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <BrainCircuit size={16} className="text-brand-400" />
            <span className="font-semibold text-slate-200">Performance Summary</span>
          </div>
          <p className="text-slate-300 text-sm leading-relaxed">
            {report.overall_summary ?? 'No summary generated. The interview may have been ended early.'}
          </p>
        </div>
      </div>

      {/* Charts */}
      {competencyData.length > 0 && (
        <div className="grid grid-cols-2 gap-5 mb-8">
          {/* Bar chart */}
          <div className="glass rounded-2xl p-6">
            <h2 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <TrendingUp size={16} className="text-brand-400" /> Competency Scores
            </h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={competencyData} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#252541" />
                <XAxis dataKey="competency" tick={{ fontSize: 10, fill: '#64748b' }} />
                <YAxis domain={[0, 4]} tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip content={CUSTOM_TOOLTIP as unknown as React.FC} />
                <Bar dataKey="score" fill="#6366f1" radius={[4, 4, 0, 0]}
                  label={{ position: 'top', fontSize: 9, fill: '#94a3b8',
                    formatter: (v: number) => v.toFixed(1) }} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Radar chart */}
          {radarData.length >= 3 && (
            <div className="glass rounded-2xl p-6">
              <h2 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
                <Award size={16} className="text-brand-400" /> Skill Radar
              </h2>
              <ResponsiveContainer width="100%" height={200}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#252541" />
                  <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10, fill: '#64748b' }} />
                  <Radar name="Score" dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.25} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Strengths & Gaps */}
      <div className="grid grid-cols-2 gap-5 mb-8">
        <div className="glass rounded-2xl p-6">
          <h2 className="font-semibold text-emerald-400 mb-4 flex items-center gap-2">
            <CheckCircle2 size={16} /> Technical Strengths
          </h2>
          {(report.technical_strengths ?? []).length === 0
            ? <p className="text-slate-500 text-sm">None identified — more questions may help.</p>
            : <ul className="space-y-2">
                {(report.technical_strengths ?? []).map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-emerald-300 opacity-85">
                    <span className="mt-1 flex-shrink-0">✓</span>{s}
                  </li>
                ))}
              </ul>}
        </div>
        <div className="glass rounded-2xl p-6">
          <h2 className="font-semibold text-red-400 mb-4 flex items-center gap-2">
            <XCircle size={16} /> Knowledge Gaps
          </h2>
          {(report.knowledge_gaps ?? []).length === 0
            ? <p className="text-slate-500 text-sm">No significant gaps detected.</p>
            : <ul className="space-y-2">
                {(report.knowledge_gaps ?? []).map((g, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-red-300 opacity-85">
                    <AlertTriangle size={12} className="mt-0.5 flex-shrink-0" />{g}
                  </li>
                ))}
              </ul>}
        </div>
      </div>

      {/* Study recommendations */}
      {(report.recommended_study_areas ?? []).length > 0 && (
        <div className="glass rounded-2xl p-6 mb-8">
          <h2 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <BookOpen size={16} className="text-brand-400" /> Recommended Study Areas
          </h2>
          <div className="grid grid-cols-2 gap-4">
            {(report.recommended_study_areas ?? []).map((area, i) => (
              <div key={i} className="glass rounded-xl p-4">
                <p className="text-slate-200 font-medium text-sm mb-1">{area.topic}</p>
                <p className="text-slate-400 text-xs mb-2 leading-relaxed">{area.reason}</p>
                <span className="badge badge-blue text-xs">{area.resources_hint}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-question breakdown */}
      {evaluations.length > 0 && (
        <div className="glass rounded-2xl p-6">
          <h2 className="font-semibold text-slate-200 mb-5 flex items-center gap-2">
            Q&amp;A Breakdown
          </h2>
          <div className="space-y-4">
            {evaluations.map((ev, i) => {
              const pct = Math.round(ev.overall_score / 4 * 100)
              const color = pct >= 70 ? 'text-emerald-400' : pct >= 45 ? 'text-amber-400' : 'text-red-400'
              return (
                <div key={i} className="glass rounded-xl p-4">
                  <div className="flex items-start gap-3 mb-3">
                    <span className="w-6 h-6 rounded-lg bg-brand-900/50 text-brand-400 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                      {i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-slate-200 text-sm font-medium leading-snug">{ev.question_text}</p>
                      <span className="badge badge-gray text-xs mt-1">{ev.competency}</span>
                    </div>
                    <span className={`font-bold text-lg ${color} flex-shrink-0`}>
                      {ev.skipped ? '—' : `${pct}%`}
                    </span>
                  </div>
                  {ev.skipped
                    ? <p className="text-xs text-slate-500 ml-9">Skipped</p>
                    : <>
                        {ev.answer_text && (
                          <div className="ml-9 mb-2 p-3 rounded-lg bg-surface-700/50 text-xs text-slate-400 italic leading-relaxed">
                            "{ev.answer_text.slice(0, 300)}{ev.answer_text.length > 300 ? '…' : ''}"
                          </div>
                        )}
                        <p className="ml-9 text-xs text-slate-400 leading-relaxed">{ev.evaluator_feedback}</p>
                      </>}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
