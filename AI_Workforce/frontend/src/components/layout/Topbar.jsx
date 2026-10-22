import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Menu, Search, Bell, LogOut } from 'lucide-react'

function Topbar({ onMenuClick }) {
  const navigate = useNavigate()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [userName, setUserName] = useState(localStorage.getItem('userName') || 'John Doe')

  useEffect(() => {
    const sync = () => setUserName(localStorage.getItem('userName') || 'John Doe')
    window.addEventListener('userNameChanged', sync)
    return () => window.removeEventListener('userNameChanged', sync)
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('isAuthenticated')
    localStorage.removeItem('accessToken')
    localStorage.removeItem('userName')
    navigate('/login')
  }

  return (
    <div className="bg-white border-b border-border-light px-8 py-4 flex items-center justify-between">
      <div className="flex items-center gap-4 flex-1">
        <button onClick={onMenuClick} className="text-text-secondary hover:text-text-primary">
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex-1 max-w-xs">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-secondary" />
            <input
              type="text"
              placeholder="Search projects, tasks, documents..."
              className="input-field pl-10 py-2 text-sm w-full"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <button className="text-text-secondary hover:text-text-primary relative">
          <Bell className="w-5 h-5" />
          <span className="absolute top-0 right-0 w-2 h-2 bg-status-danger rounded-full"></span>
        </button>

        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 hover:bg-gray-50 px-3 py-2 rounded-lg transition-colors"
          >
            <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center text-white text-xs font-bold">
              {userName.charAt(0).toUpperCase()}
            </div>
            <span className="text-sm font-medium text-text-primary">{userName}</span>
          </button>

          {showUserMenu && (
            <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg border border-border-light shadow-lg z-50">
              <div className="p-4 border-b border-border-light">
                <div className="text-sm font-medium text-text-primary">{userName}</div>
                <div className="text-xs text-text-secondary">john@example.com</div>
              </div>
              <button
                onClick={handleLogout}
                className="w-full text-left px-4 py-2 text-sm text-text-secondary hover:bg-gray-50 flex items-center gap-2"
              >
                <LogOut className="w-4 h-4" />
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Topbar
