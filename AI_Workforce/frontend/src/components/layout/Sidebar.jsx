import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, Folder, CheckSquare, Bot, Code2, FileText, BarChart3, Zap, Settings } from 'lucide-react'

function Sidebar({ isOpen }) {
  const location = useLocation()

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/projects', label: 'Projects', icon: Folder },
    { path: '/documents', label: 'Documents', icon: FileText },
    { path: '/agents', label: 'AI Agents', icon: Bot },
    { path: '/developer', label: 'Developer AI', icon: Code2 },
    { path: '/tasks', label: 'Tasks', icon: CheckSquare },
    { path: '/reports', label: 'Reports', icon: BarChart3 },
    { path: '/integrations', label: 'Integrations', icon: Zap },
    { path: '/settings', label: 'Settings', icon: Settings },
  ]

  const isActive = (path) => location.pathname === path

  return (
    <div className={`${isOpen ? 'w-64' : 'w-20'} bg-white border-r border-border-light transition-all duration-300 flex flex-col overflow-hidden`}>
      <div className="p-6 border-b border-border-light">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center flex-shrink-0">
            <Bot className="w-6 h-6 text-white" />
          </div>
          {isOpen && (
            <div>
              <div className="font-bold text-text-primary text-sm">AI Workforce</div>
              <div className="text-xs text-text-secondary">SDLC Automation</div>
            </div>
          )}
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto p-4 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = isActive(item.path)

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                active
                  ? 'bg-primary-light text-primary'
                  : 'text-text-secondary hover:bg-gray-50'
              }`}
              title={isOpen ? '' : item.label}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {isOpen && <span className="text-sm font-medium">{item.label}</span>}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}

export default Sidebar
