import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getMatch, type MatchReportResponse, type SkillResult } from '../api/client'
import {
  CheckCircle2, XCircle, AlertTriangle, HelpCircle, ArrowRight,
  Loader2, TrendingUp, Target, Layers, Zap, Info
} from 'lucide-react'
import clsx from 'clsx'

function SkillPill({ s }: { s: SkillResult }) {
  const map: Record<string, string> = {
    exact: 'badge-green', alias: 'badge-green', fuzzy: 'badge-blue',
    semantic: 'badge-purple', not_found: 'badge-red', ambiguous: 'badge-yellow',
  }
  const icon: Record<string, React.ReactNode> = {
    exact: <CheckCircle2 size={10} />, alias: <CheckCircle2 size={10} />,
    fuzzy: <CheckCircle2 size={10} />, semantic: <CheckCircle2 size={10} />,
    not_found: <XCircle size={10} />, ambiguous: <AlertTriangle size={10} />,
  }
  return (
    <div title={s.evidence ?? s.notes ?? ''} className={`badge ${map[s.status] ?? 'badge-gray'} cursor-help`}>
      {icon[s.status] ?? <HelpCircle size={10} />}
      {s.jd_skill}
    </div>
  )
}

function ScoreBar({ label, value, max = 1 }: { label: string; value: number; max?: number }) {
  const pct = Math.round((value / max) * 100)
  const color = pct >= 70 ? 'bg-emerald-500' : pct >= 45 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div>
      <div className="flex justify-between text-xs mb-1.5">
        <span className="text-slate-400">{label}</span>
        <span className="text-slate-300 font-medium">{pct}%</span>
      </div>
      <div className="score-bar">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function MatchAnalysis() {
  const { matchId } = useParams<{ matchId: string }>()
  const navigate = useNavigate()
  const [match, setMatch] = useState<MatchReportResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!matchId) return
    getMatch(matchId)
      .then(r => setMatch(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [matchId])

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <Loader2 size={36} className="animate-spin text-brand-400" />
    </div>
  )

  if (!match) return (
    <div className="p-8">
      <p className="text-slate-400">Match report not found.</p>
      <button onClick={() => navigate('/')} className="btn-secondary mt-4">← Dashboard</button>
    </div>
  )

  const req = match.skill_analysis?.required ?? []
  const pref = match.skill_analysis?.preferred ?? []
  const reqMatched = req.filter(s => !['not_found'].includes(s.status))
  const reqMissing = req.filter(s => s.status === 'not_found')
  const reqAmbiguous = req.filter(s => s.status === 'ambiguous')

  return (
    <div className="p-8 animate-fade-in max-w-4xl">
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold gradient-text mb-1">Match Analysis</h1>
          <p className="text-slate-400 text-sm">Resume–JD alignment report</p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => navigate(-1)} className="btn-secondary">← Back</button>
          <button onClick={() => navigate('/new')} className="btn-primary">
            <Zap size={14} /> Start Interview
          </button>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-900/20 border border-amber-500/20 text-xs text-amber-300 mb-8">
        <Info size={14} className="flex-shrink-0 mt-0.5" />
        Scores reflect textual overlap and semantic similarity — not validated predictors of job performance.
      </div>

      {/* Score overview */}
      <div className="grid grid-cols-2 gap-5 mb-8">
        <div className="glass rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={18} className="text-brand-400" />
            <span className="font-semibold text-slate-200">Overall Alignment</span>
          </div>
          <div className="flex items-end gap-3 mb-5">
            <span className="text-5xl font-bold text-slate-100">{Math.round(match.overall_score ?? 0)}</span>
            <span className="text-slate-400 mb-2">/100</span>
          </div>
          <div className="space-y-3">
            <ScoreBar label="Required skill coverage" value={match.required_skill_coverage ?? 0} />
            <ScoreBar label="Preferred skill coverage" value={match.preferred_skill_coverage ?? 0} />
          </div>
        </div>

        <div className="glass rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Target size={18} className="text-brand-400" />
            <span className="font-semibold text-slate-200">Required Skills</span>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-emerald-400">{reqMatched.length}</p>
              <p className="text-xs text-slate-500 mt-0.5">Matched</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-amber-400">{reqAmbiguous.length}</p>
              <p className="text-xs text-slate-500 mt-0.5">Ambiguous</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-red-400">{reqMissing.length}</p>
              <p className="text-xs text-slate-500 mt-0.5">Missing</p>
            </div>
          </div>
          <div className="score-bar h-2">
            <div className="h-full rounded-full bg-emerald-500 transition-all duration-700"
              style={{ width: `${req.length ? reqMatched.length / req.length * 100 : 0}%` }} />
          </div>
        </div>
      </div>

      {/* Required skills breakdown */}
      <div className="glass rounded-2xl p-6 mb-5">
        <h2 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <Target size={16} className="text-brand-400" /> Required Skills
        </h2>
        <div className="flex flex-wrap gap-2">
          {req.map((s, i) => <SkillPill key={i} s={s} />)}
          {req.length === 0 && <p className="text-slate-500 text-sm">No required skills extracted.</p>}
        </div>
      </div>

      {pref.length > 0 && (
        <div className="glass rounded-2xl p-6 mb-5">
          <h2 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <Layers size={16} className="text-brand-400" /> Preferred Skills
          </h2>
          <div className="flex flex-wrap gap-2">
            {pref.map((s, i) => <SkillPill key={i} s={s} />)}
          </div>
        </div>
      )}

      {/* Strengths & Gaps */}
      <div className="grid grid-cols-2 gap-5 mb-5">
        {[
          { title: 'Strengths', items: match.strengths ?? [], color: 'text-emerald-400', Icon: CheckCircle2 },
          { title: 'Gaps & Missing Skills', items: match.gaps ?? [], color: 'text-red-400', Icon: XCircle },
        ].map(({ title, items, color, Icon }) => (
          <div key={title} className="glass rounded-2xl p-6">
            <h2 className={`font-semibold mb-4 flex items-center gap-2 ${color}`}>
              <Icon size={16} /> {title}
            </h2>
            {items.length === 0
              ? <p className="text-slate-500 text-sm">None identified.</p>
              : <ul className="space-y-2">
                  {items.map((item, i) => (
                    <li key={i} className={`text-xs ${color} opacity-80 flex items-start gap-1.5`}>
                      <span className="mt-0.5">•</span>{item}
                    </li>
                  ))}
                </ul>}
          </div>
        ))}
      </div>

      {/* Suggested interview topics */}
      {(match.suggested_topics ?? []).length > 0 && (
        <div className="glass rounded-2xl p-6">
          <h2 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <ArrowRight size={16} className="text-brand-400" /> Suggested Interview Topics
          </h2>
          <div className="flex flex-wrap gap-2">
            {(match.suggested_topics ?? []).map((t, i) => (
              <span key={i} className="badge badge-purple text-xs">{t}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
