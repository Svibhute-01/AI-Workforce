import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import '../../styles/app-theme.css'

const isDesktop = () => typeof window === 'undefined' || window.innerWidth >= 1024

function MainLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(isDesktop)
  const location = useLocation()

  useEffect(() => {
    if (!isDesktop()) setSidebarOpen(false)
  }, [location.pathname])

  return (
    <div className="app-shell flex h-screen">
      <div className="bt-deco" aria-hidden="true">
        <span className="bt-blob b1" />
        <span className="bt-blob b2" />
        <span className="bt-blob b3" />
        <span className="bt-spark s1" />
        <span className="bt-spark s2" />
        <span className="bt-spark s3" />
        <span className="bt-spark s4" />
        <span className="bt-spark s5" />
        <span className="bt-dot d1" />
        <span className="bt-dot d2" />
        <span className="bt-dot d3" />
      </div>

      <Sidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />

      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-brand-ink/40 backdrop-blur-sm lg:hidden"
        />
      )}

      <div className="relative z-[1] flex min-w-0 flex-1 flex-col overflow-hidden">
        <Topbar onMenuClick={() => setSidebarOpen(!sidebarOpen)} />

        <main className="flex-1 overflow-auto">
          <div key={location.pathname} className="bt-page mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}

export default MainLayout
