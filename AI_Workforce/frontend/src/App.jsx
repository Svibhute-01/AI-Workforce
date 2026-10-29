import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Projects from './pages/Projects'
import ProjectDetails from './pages/ProjectDetails'
import Tasks from './pages/Tasks'
import AIAgents from './pages/AIAgents'
import Developer from './pages/Developer'
import AIChat from './pages/AIChat'
import Documents from './pages/Documents'
import Reports from './pages/Reports'
import Settings from './pages/Settings'
import PrivateRoute from './components/layout/PrivateRoute'

function RootRoute() {
  const isAuthenticated = localStorage.getItem('accessToken') || localStorage.getItem('isAuthenticated')
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <Landing />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        <Route path="/" element={<RootRoute />} />
        <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/projects" element={<PrivateRoute><Projects /></PrivateRoute>} />
        <Route path="/projects/:id" element={<PrivateRoute><ProjectDetails /></PrivateRoute>} />
        <Route path="/tasks" element={<PrivateRoute><Tasks /></PrivateRoute>} />
        <Route path="/agents" element={<PrivateRoute><AIAgents /></PrivateRoute>} />
        <Route path="/developer" element={<PrivateRoute fullScreen><Developer /></PrivateRoute>} />
        <Route path="/chat" element={<PrivateRoute><AIChat /></PrivateRoute>} />
        <Route path="/documents" element={<PrivateRoute><Documents /></PrivateRoute>} />
        <Route path="/reports" element={<PrivateRoute><Reports /></PrivateRoute>} />
        <Route path="/integrations" element={<Navigate to="/settings?section=integrations" replace />} />
        <Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
