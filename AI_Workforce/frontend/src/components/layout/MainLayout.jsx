import { useState } from 'react'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

function MainLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="flex h-screen bg-bg-light">
      <Sidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar onMenuClick={() => setSidebarOpen(!sidebarOpen)} />
        
        <main className="flex-1 overflow-auto">
          <div className="p-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}

export default MainLayout
