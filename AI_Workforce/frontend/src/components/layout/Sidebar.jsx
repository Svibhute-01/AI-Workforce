import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, Folder, CheckSquare, Bot, Code2, FileText, BarChart3, Zap, Settings, MessageCircle } from 'lucide-react'
import BrandMark from '../brand/BrandMark'
import apiService from '../../services/api'

const NAV_ITEMS = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/projects', label: 'Projects', icon: Folder },
  { path: '/documents', label: 'Documents', icon: FileText },
  { path: '/agents', label: 'AI Agents', icon: Bot },
  { path: '/chat', label: 'Project Chat', icon: MessageCircle },
  { path: '/developer', label: 'Developer AI', icon: Code2 },
  { path: '/tasks', label: 'Tasks', icon: CheckSquare },
  { path: '/reports', label: 'Reports', icon: BarChart3 },
  { path: '/integrations', label: 'Integrations', icon: Zap },
  { path: '/settings', label: 'Settings', icon: Settings },
]

const HEALTH_LABEL = { checking: 'Checking API…', online: 'API online', offline: 'API unreachable' }

function useApiHealth() {
  const [state, setState] = useState('checking')

  useEffect(() => {
    let cancelled = false
    const check = () => {
      apiService.health()
        .then((ok) => { if (!cancelled) setState(ok ? 'online' : 'offline') })
        .catch(() => { if (!cancelled) setState('offline') })
    }
    check()
    const timer = setInterval(check, 30000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  return state
}

function Sidebar({ isOpen }) {
  const location = useLocation()
  const health = useApiHealth()

  const isActive = (path) => location.pathname === path || location.pathname.startsWith(`${path}/`)
  const dot = health === 'online' ? 'bg-green-500 bt-live' : health === 'offline' ? 'bg-red-500' : 'bg-brand-deep'

  return (
    <aside
      className={`app-sidebar relative z-[1] flex flex-col overflow-hidden transition-all duration-200
        fixed inset-y-0 left-0 z-40 lg:static lg:z-[1]
        ${isOpen ? 'w-64 translate-x-0' : 'w-64 -translate-x-full lg:w-[4.5rem] lg:translate-x-0'}`}
    >
      <div className="flex h-16 shrink-0 items-center border-b border-brand-deep/60 px-4">
        <div className="flex min-w-0 items-center gap-3">
          <BrandMark size={40} className="shrink-0 drop-shadow" />
          {isOpen && (
            <div className="min-w-0">
              <div className="truncate text-sm font-extrabold leading-tight text-brand-ink">AI Workforce</div>
              <div className="truncate text-[11px] font-semibold leading-tight text-brand-ink/70">SDLC Automation</div>
            </div>
          )}
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4" aria-label="Primary">
        {isOpen && <p className="px-3 pb-2 text-[10px] font-extrabold uppercase tracking-widest text-brand-ink/60">Workspace</p>}
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const active = isActive(item.path)

          return (
            <Link
              key={item.path}
              to={item.path}
              aria-current={active ? 'page' : undefined}
              className="nav-link flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold"
              title={isOpen ? '' : item.label}
            >
              <Icon className="nav-icon h-[18px] w-[18px] flex-shrink-0" />
              {isOpen && <span className="truncate">{item.label}</span>}
            </Link>
          )
        })}
      </nav>

      <div className="relative shrink-0 border-t border-brand-deep/60 p-3">
        <div className={`flex items-center gap-2 rounded-xl bg-brand-lemon/70 px-3 py-2 text-xs font-bold text-brand-ink ${isOpen ? '' : 'justify-center px-0'}`} role="status" title={HEALTH_LABEL[health]}>
          <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${dot}`} />
          {isOpen && <span className="truncate">{HEALTH_LABEL[health]}</span>}
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
