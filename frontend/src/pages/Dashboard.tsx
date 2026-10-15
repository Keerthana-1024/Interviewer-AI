import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  listSessions, deleteSession, getReport,
  type SessionState, type FinalReport
} from '../api/client'
import {
  PlusCircle, Trash2, ChevronRight, Clock, CheckCircle2,
  PauseCircle, XCircle, BarChart3, BrainCircuit, TrendingUp,
  Calendar, Loader2
} from 'lucide-react'
import clsx from 'clsx'

const STATUS_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  active:    { label: 'In Progress',  color: 'badge-blue',   icon: <Clock size={10} /> },
  paused:    { label: 'Paused',       color: 'badge-yellow', icon: <PauseCircle size={10} /> },
  completed: { label: 'Completed',    color: 'badge-green',  icon: <CheckCircle2 size={10} /> },
  abandoned: { label: 'Abandoned',    color: 'badge-red',    icon: <XCircle size={10} /> },
  pending:   { label: 'Pending',      color: 'badge-gray',   icon: <Clock size={10} /> },
}

function ScoreRing({ score }: { score: number }) {
  const pct = Math.round(score / 4 * 100)
  const r = 28
  const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ
  const color = pct >= 70 ? '#10b981' : pct >= 45 ? '#f59e0b' : '#ef4444'

  return (
    <svg width="72" height="72" viewBox="0 0 72 72">
      <circle cx="36" cy="36" r={r} fill="none" stroke="#1e1e35" strokeWidth="6" />
      <circle cx="36" cy="36" r={r} fill="none" stroke={color} strokeWidth="6"
        strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round"
        transform="rotate(-90 36 36)" style={{ transition: 'stroke-dasharray 0.6s ease' }} />
      <text x="36" y="40" textAnchor="middle" fill="white" fontSize="13" fontWeight="700">{pct}%</text>
    </svg>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<SessionState[]>([])
  const [reports, setReports] = useState<Record<string, FinalReport>>({})
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)

  useEffect(() => {
    loadSessions()
  }, [])

  async function loadSessions() {
    setLoading(true)
    try {
      const { data } = await listSessions()
      setSessions(data)
      // Load reports for completed sessions
      const reps: Record<string, FinalReport> = {}
      await Promise.allSettled(
        data.filter(s => s.status === 'completed').map(async s => {
          try {
            const r = await getReport(s.id)
            reps[s.id] = r.data
          } catch {}
        })
      )
      setReports(reps)
    } catch {
      setSessions([])
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(id: string) {
    setDeleting(id)
    try {
      await deleteSession(id)
      setSessions(prev => prev.filter(s => s.id !== id))
    } finally {
      setDeleting(null)
    }
  }

  function handleOpen(s: SessionState) {
    if (s.status === 'completed') navigate(`/results/${s.id}`)
    else navigate(`/interview/${s.id}`)
  }

  const completed = sessions.filter(s => s.status === 'completed')
  const avgScore = completed.length
    ? completed.reduce((acc, s) => acc + (reports[s.id]?.overall_score ?? 0), 0) / completed.length
    : 0

  return (
    <div className="p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-10">
        <div>
          <h1 className="text-3xl font-bold gradient-text mb-1">Dashboard</h1>
          <p className="text-slate-400 text-sm">Your interview practice history and performance overview</p>
        </div>
        <button onClick={() => navigate('/new')} className="btn-primary">
          <PlusCircle size={16} /> New Interview
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-5 mb-10">
        {[
          {
            label: 'Total Sessions', value: sessions.length,
            icon: <BrainCircuit size={20} className="text-brand-400" />,
            sub: `${sessions.filter(s => s.status === 'active' || s.status === 'paused').length} in progress`,
          },
          {
            label: 'Completed', value: completed.length,
            icon: <CheckCircle2 size={20} className="text-emerald-400" />,
            sub: `${sessions.filter(s => s.status === 'paused').length} paused`,
          },
          {
            label: 'Avg. Score', value: completed.length ? `${Math.round(avgScore / 4 * 100)}%` : '—',
            icon: <TrendingUp size={20} className="text-amber-400" />,
            sub: completed.length ? `across ${completed.length} sessions` : 'Complete an interview first',
          },
        ].map(stat => (
          <div key={stat.label} className="glass rounded-2xl p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 rounded-xl bg-surface-600">{stat.icon}</div>
              <span className="text-sm text-slate-400">{stat.label}</span>
            </div>
            <p className="text-3xl font-bold text-slate-100">{stat.value}</p>
            <p className="text-xs text-slate-500 mt-1">{stat.sub}</p>
          </div>
        ))}
      </div>

      {/* Sessions list */}
      <h2 className="text-lg font-semibold text-slate-200 mb-4 flex items-center gap-2">
        <BarChart3 size={18} className="text-brand-400" /> Recent Sessions
      </h2>

      {loading ? (
        <div className="flex items-center justify-center h-48 glass rounded-2xl">
          <Loader2 className="animate-spin text-brand-400" size={28} />
        </div>
      ) : sessions.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center">
          <BrainCircuit size={48} className="text-brand-600 mx-auto mb-4 opacity-50" />
          <p className="text-slate-400 mb-2 font-medium">No interviews yet</p>
          <p className="text-slate-500 text-sm mb-6">Upload your resume and a job description to get started</p>
          <button onClick={() => navigate('/new')} className="btn-primary mx-auto">
            <PlusCircle size={15} /> Start your first interview
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map(s => {
            const meta = STATUS_META[s.status] ?? STATUS_META.pending
            const report = reports[s.id]
            return (
              <div key={s.id}
                className="glass rounded-2xl p-5 flex items-center gap-5 hover:border-brand-600/30 transition-all duration-200 group cursor-pointer"
                onClick={() => handleOpen(s)}>
                {/* Score ring */}
                <div className="flex-shrink-0">
                  {report?.overall_score != null
                    ? <ScoreRing score={report.overall_score} />
                    : <div className="w-[72px] h-[72px] rounded-full bg-surface-700 flex items-center justify-center">
                        <span className="text-xs text-slate-500">—</span>
                      </div>}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`badge ${meta.color} gap-1`}>{meta.icon}{meta.label}</span>
                    {s.config && <span className="badge badge-gray">{(s.config as Record<string,string>).mode}</span>}
                    {s.config && <span className="badge badge-gray">{(s.config as Record<string,string>).difficulty}</span>}
                  </div>
                  <p className="text-slate-200 font-medium truncate">
                    {s.candidate_name ?? 'Anonymous candidate'}
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                      <Calendar size={10} /> {new Date(s.created_at).toLocaleDateString()}
                    </span>
                    <span>{s.current_question_index}/{s.total_questions} questions</span>
                    {report && <span className="text-brand-400 font-medium">Score: {Math.round((report.overall_score ?? 0) / 4 * 100)}%</span>}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button onClick={e => { e.stopPropagation(); handleDelete(s.id) }}
                    className="p-2 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-900/20 transition-colors"
                    disabled={deleting === s.id}>
                    {deleting === s.id
                      ? <Loader2 size={15} className="animate-spin" />
                      : <Trash2 size={15} />}
                  </button>
                  <ChevronRight size={18} className="text-slate-600 group-hover:text-brand-400 transition-colors" />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
