import { Navigate } from 'react-router-dom'
import MainLayout from './MainLayout'

// fullScreen pages (the Developer workspace) fill the whole window instead of sitting inside the app shell.
function PrivateRoute({ children, fullScreen = false }) {
  const isAuthenticated = localStorage.getItem('accessToken') || localStorage.getItem('isAuthenticated')

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (fullScreen) {
    return <div className="h-screen w-screen overflow-hidden">{children}</div>
  }

  return <MainLayout>{children}</MainLayout>
}

export default PrivateRoute
