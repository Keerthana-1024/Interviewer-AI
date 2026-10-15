import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { BrainCircuit, LayoutDashboard, PlusCircle, ChevronRight } from 'lucide-react'
import clsx from 'clsx'

export default function Layout() {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen bg-surface-900">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 glass-strong border-r border-white/5 flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-white/5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center shadow-lg shadow-brand-900/50">
            <BrainCircuit size={20} className="text-white" />
          </div>
          <div>
            <p className="font-bold text-slate-100 leading-tight">AI Interviewer</p>
            <p className="text-xs text-slate-500">Resume-aware platform</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          <NavLink to="/" end className={({ isActive }) =>
            clsx('flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150',
              isActive
                ? 'bg-brand-600/20 text-brand-300 border border-brand-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-surface-700')}>
            <LayoutDashboard size={16} />
            Dashboard
          </NavLink>
          <NavLink to="/new" className={({ isActive }) =>
            clsx('flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150',
              isActive
                ? 'bg-brand-600/20 text-brand-300 border border-brand-600/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-surface-700')}>
            <PlusCircle size={16} />
            New Interview
          </NavLink>
        </nav>

        {/* Footer */}
        <div className="px-4 py-4 border-t border-white/5">
          <div className="glass rounded-xl p-3">
            <p className="text-xs text-slate-500 leading-relaxed">
              Practice tool only. Not a hiring decision system.
            </p>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
