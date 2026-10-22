import { Navigate } from 'react-router-dom'
import MainLayout from './MainLayout'

function PrivateRoute({ children }) {
  const isAuthenticated = localStorage.getItem('accessToken') || localStorage.getItem('isAuthenticated')

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <MainLayout>{children}</MainLayout>
}

export default PrivateRoute
