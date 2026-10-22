import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import apiService from '../services/api'

function Login() {
  const navigate = useNavigate()
  const [isRegistering, setIsRegistering] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email || !password) {
      setError('Please fill in all fields')
      return
    }

    if (!email.includes('@')) {
      setError('Please enter a valid email')
      return
    }

    if (isRegistering && password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setIsSubmitting(true)
    setError('')
    try {
      const result = isRegistering
        ? await apiService.auth.register({
            email,
            password,
            display_name: displayName || email.split('@')[0],
          })
        : await apiService.auth.login({ email, password })
      localStorage.setItem('accessToken', result.access_token)
      localStorage.setItem('isAuthenticated', 'true')
      localStorage.setItem('userName', result.user.display_name)
      navigate('/dashboard')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex h-screen bg-white">
      <div className="hidden lg:flex w-1/2 bg-gradient-to-br from-primary to-primary-dark text-white p-12 flex-col justify-between relative overflow-hidden">
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-white rounded-lg flex items-center justify-center">
              <div className="text-primary font-bold text-lg">AI</div>
            </div>
            <div>
              <div className="text-2xl font-bold">AI Workforce</div>
              <div className="text-sm opacity-90">SDLC Automation Platform</div>
            </div>
          </div>

          <div className="mt-16">
            <h2 className="text-4xl font-bold mb-4">Automate Your Development</h2>
            <p className="text-lg opacity-90">Collaborate with AI agents to accelerate your software development lifecycle</p>
          </div>
        </div>

        <div className="relative z-10">
          <p className="text-sm opacity-75">AI Workforce - Intelligent Automation Platform 2024</p>
        </div>

        <div className="absolute top-0 right-0 w-96 h-96 bg-white opacity-5 rounded-full transform translate-x-1/2 -translate-y-1/2"></div>
      </div>

      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-bg-light">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-text-primary mb-2">{isRegistering ? 'Create Account' : 'Welcome Back'}</h1>
            <p className="text-text-secondary">{isRegistering ? 'Create your AI Workforce account' : 'Sign in to your account'}</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            {isRegistering && (
              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">Display Name</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="input-field"
                  placeholder="Your name"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-text-primary mb-2">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field"
                placeholder="Enter your email"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-text-primary mb-2">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field pr-10"
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-text-secondary hover:text-text-primary"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-4 h-4 rounded border-border-light"
                />
                <span className="text-sm text-text-secondary">Remember me</span>
              </label>
              <a href="#" className="text-sm text-primary hover:text-primary-dark">Forgot password?</a>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full"
            >
              {isSubmitting ? 'Connecting...' : isRegistering ? 'Create Account' : 'Sign In'}
            </button>

            <p className="text-center text-text-secondary text-sm">
              {isRegistering ? 'Already have an account? ' : "Don't have an account? "}
              <button
                type="button"
                onClick={() => {
                  setIsRegistering(!isRegistering)
                  setError('')
                }}
                className="text-primary hover:text-primary-dark font-medium"
              >
                {isRegistering ? 'Sign In' : 'Sign Up'}
              </button>
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}

export default Login
