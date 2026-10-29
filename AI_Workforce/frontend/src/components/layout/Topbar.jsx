import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Bell, CheckCircle, Folder, Info, LogOut, Menu, Search } from 'lucide-react'
import apiService from '../../services/api'

function useOutsideClick(ref, active, close) {
  useEffect(() => {
    if (!active) return undefined
    const handler = (event) => {
      if (ref.current && !ref.current.contains(event.target)) close()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [ref, active, close])
}

function Topbar({ onMenuClick }) {
  const navigate = useNavigate()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [showAlerts, setShowAlerts] = useState(false)
  const [userName, setUserName] = useState(localStorage.getItem('userName') || 'Account')
  const [alerts, setAlerts] = useState(null)
  const [projects, setProjects] = useState([])
  const [query, setQuery] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const menuRef = useRef(null)
  const alertRef = useRef(null)
  const searchRef = useRef(null)

  const closeMenu = useCallback(() => setShowUserMenu(false), [])
  const closeAlerts = useCallback(() => setShowAlerts(false), [])
  const closeSearch = useCallback(() => setSearchOpen(false), [])

  useEffect(() => {
    const sync = () => setUserName(localStorage.getItem('userName') || 'Account')
    window.addEventListener('userNameChanged', sync)
    return () => window.removeEventListener('userNameChanged', sync)
  }, [])

  const loadAlerts = useCallback(() => {
    apiService.dashboard.getSummary()
      .then((summary) => setAlerts(summary?.insights?.attention || []))
      .catch(() => setAlerts(null))
  }, [])

  useEffect(() => {
    loadAlerts()
    const timer = setInterval(loadAlerts, 60000)
    return () => clearInterval(timer)
  }, [loadAlerts])

  useEffect(() => {
    apiService.projects.getAll().then(setProjects).catch(() => setProjects([]))
  }, [])

  useOutsideClick(menuRef, showUserMenu, closeMenu)
  useOutsideClick(alertRef, showAlerts, closeAlerts)
  useOutsideClick(searchRef, searchOpen, closeSearch)

  const matches = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return []
    return projects.filter((project) => project.name.toLowerCase().includes(term)).slice(0, 6)
  }, [projects, query])

  const openProject = (id) => {
    setQuery('')
    setSearchOpen(false)
    navigate(`/projects/${id}`)
  }

  const handleLogout = () => {
    localStorage.removeItem('isAuthenticated')
    localStorage.removeItem('accessToken')
    localStorage.removeItem('userName')
    navigate('/login')
  }

  const alertCount = alerts?.length || 0

  return (
    <header className="app-topbar relative z-20 flex h-16 shrink-0 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button
          onClick={onMenuClick}
          aria-label="Toggle navigation"
          className="-ml-2 rounded-xl p-2 text-text-secondary transition-colors hover:bg-brand-soft/70 hover:text-text-primary"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="relative hidden max-w-sm flex-1 sm:block" ref={searchRef}>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
          <input
            type="search"
            aria-label="Search projects"
            placeholder="Search projects..."
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSearchOpen(true) }}
            onFocus={() => setSearchOpen(true)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && matches[0]) openProject(matches[0].id)
              if (e.key === 'Escape') setSearchOpen(false)
            }}
            className="input-field w-full py-2 pl-10 text-sm"
          />
          {searchOpen && query.trim() && (
            <div className="card absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden p-1" role="listbox">
              {matches.length === 0 ? (
                <p className="px-3 py-3 text-sm text-text-secondary">No projects match &ldquo;{query.trim()}&rdquo;</p>
              ) : matches.map((project) => (
                <button
                  key={project.id}
                  role="option"
                  onClick={() => openProject(project.id)}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-text-primary transition-colors hover:bg-brand-soft/70"
                >
                  <Folder className="h-4 w-4 shrink-0 text-primary" />
                  <span className="truncate">{project.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <div className="relative" ref={alertRef}>
          <button
            aria-label={alertCount ? `Notifications, ${alertCount} need attention` : 'Notifications'}
            aria-haspopup="menu"
            aria-expanded={showAlerts}
            onClick={() => { setShowAlerts(!showAlerts); if (!showAlerts) loadAlerts() }}
            className="relative rounded-xl p-2 text-text-secondary transition-colors hover:bg-brand-soft/70 hover:text-text-primary"
          >
            <Bell className="h-5 w-5" />
            {alertCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-[1rem] place-items-center rounded-full border border-brand-ink bg-brand-golden px-1 text-[10px] font-extrabold text-brand-ink">
                {alertCount > 9 ? '9+' : alertCount}
              </span>
            )}
          </button>

          {showAlerts && (
            <div role="menu" className="card absolute right-0 z-50 mt-2 w-80 max-w-[85vw] overflow-hidden">
              <div className="border-b border-border-light px-4 py-3 text-sm font-extrabold text-text-primary">Needs attention</div>
              <div className="max-h-80 overflow-y-auto">
                {alerts === null ? (
                  <p className="px-4 py-5 text-sm text-text-secondary">Couldn&rsquo;t load notifications right now.</p>
                ) : alerts.length === 0 ? (
                  <p className="flex items-center gap-2 px-4 py-5 text-sm text-text-secondary"><CheckCircle className="h-4 w-4 text-green-600" /> All clear. Nothing needs attention.</p>
                ) : alerts.map((item, index) => (
                  <div key={index} className="flex gap-2 border-b border-border-light px-4 py-3 text-xs last:border-b-0">
                    {item.severity === 'info' ? <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-700" />}
                    <div className="min-w-0">
                      <p className="font-bold text-text-primary">{item.title} <span className="font-normal text-text-secondary">· {item.project_name}</span></p>
                      {item.detail && <p className="text-text-secondary">{item.detail}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            aria-haspopup="menu"
            aria-expanded={showUserMenu}
            className="flex items-center gap-2 rounded-xl px-2 py-1.5 transition-colors hover:bg-brand-soft/70 sm:px-3"
          >
            <div className="grid h-8 w-8 place-items-center rounded-full border-2 border-brand-ink bg-gradient-to-br from-brand-lemon to-brand-golden text-xs font-extrabold text-brand-ink shadow">
              {userName.charAt(0).toUpperCase()}
            </div>
            <span className="hidden max-w-[10rem] truncate text-sm font-bold text-text-primary sm:inline">{userName}</span>
          </button>

          {showUserMenu && (
            <div role="menu" className="card absolute right-0 z-50 mt-2 w-52 overflow-hidden">
              <div className="border-b border-border-light px-4 py-3">
                <div className="truncate text-sm font-bold text-text-primary">{userName}</div>
                <div className="text-xs text-text-secondary">Signed in</div>
              </div>
              <button
                role="menuitem"
                onClick={handleLogout}
                className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm font-semibold text-text-secondary transition-colors hover:bg-brand-soft/70 hover:text-text-primary"
              >
                <LogOut className="h-4 w-4" />
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

export default Topbar
