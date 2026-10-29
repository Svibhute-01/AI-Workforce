import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { AlertCircle, Eye, EyeOff, Info, Loader2 } from 'lucide-react'
import apiService from '../services/api'
import { OrbitScene } from '../components/brand/AIRobot'
import BrandMark from '../components/brand/BrandMark'
import '../styles/app-theme.css'
import '../styles/login.css'

const REMEMBER_KEY = 'rememberedEmail'

const readRemembered = () => {
  try {
    return localStorage.getItem(REMEMBER_KEY) || ''
  } catch {
    return ''
  }
}

function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const remembered = readRemembered()
  const [isRegistering, setIsRegistering] = useState(location.state?.mode === 'register')
  const [email, setEmail] = useState(remembered)
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(Boolean(remembered))
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [focus, setFocus] = useState('')
  const [showReset, setShowReset] = useState(false)

  const sceneMode = error ? 'error' : focus === 'password' && !showPassword ? 'password' : 'idle'

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
      try {
        if (rememberMe) localStorage.setItem(REMEMBER_KEY, email)
        else localStorage.removeItem(REMEMBER_KEY)
      } catch {
        /* storage unavailable */
      }
      navigate('/dashboard')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="auth-shell login-page flex min-h-screen flex-col lg:flex-row">
      <div className="login-form-side order-2 flex w-full items-center justify-center p-6 sm:p-10 lg:order-1 lg:w-1/2">
        <div className="login-card card bt-page w-full max-w-md p-6 sm:p-8">
          <div className="mb-7">
            <div className="mb-6 flex items-center gap-3">
              <BrandMark size={44} />
              <div>
                <div className="text-lg font-extrabold leading-tight text-text-primary">AI Workforce</div>
                <div className="text-xs font-semibold text-text-secondary">SDLC Automation Platform</div>
              </div>
            </div>
            <h1 className="mb-1 text-2xl font-extrabold text-text-primary">{isRegistering ? 'Create your account' : 'Welcome back'}</h1>
            <p className="text-sm text-text-secondary">{isRegistering ? 'Create your AI Workforce account' : 'Sign in to continue to your workspace'}</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {error && (
              <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {isRegistering && (
              <div>
                <label htmlFor="displayName" className="mb-1.5 block text-sm font-semibold text-text-primary">Display Name</label>
                <input
                  id="displayName"
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  onFocus={() => setFocus('name')}
                  onBlur={() => setFocus('')}
                  className="input-field"
                  placeholder="Your name"
                  autoComplete="name"
                />
              </div>
            )}

            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-semibold text-text-primary">Email Address</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onFocus={() => setFocus('email')}
                onBlur={() => setFocus('')}
                className="input-field"
                placeholder="Enter your email"
                autoComplete="email"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-semibold text-text-primary">Password</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={() => setFocus('password')}
                  onBlur={() => setFocus('')}
                  className="input-field pr-11"
                  placeholder="Enter your password"
                  autoComplete={isRegistering ? 'new-password' : 'current-password'}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-0.5 text-text-secondary transition-colors hover:text-text-primary"
                >
                  {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="h-4 w-4 rounded"
                />
                <span className="text-sm text-text-secondary">Remember my email</span>
              </label>
              {!isRegistering && (
                <button type="button" onClick={() => setShowReset(!showReset)} aria-expanded={showReset} className="text-sm font-semibold text-primary underline-offset-2 hover:underline">
                  Forgot password?
                </button>
              )}
            </div>

            {showReset && !isRegistering && (
              <div className="flex items-start gap-2 rounded-xl border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Self-service password reset isn&rsquo;t available yet. Ask your workspace administrator to reset it, or sign in to Settings and change it there.</span>
              </div>
            )}

            <button type="submit" disabled={isSubmitting} className="btn-primary flex w-full items-center justify-center gap-2 py-3">
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {isSubmitting ? 'Connecting...' : isRegistering ? 'Create Account' : 'Sign In'}
            </button>

            <p className="text-center text-sm text-text-secondary">
              {isRegistering ? 'Already have an account? ' : "Don't have an account? "}
              <button
                type="button"
                onClick={() => {
                  setIsRegistering(!isRegistering)
                  setError('')
                  setShowReset(false)
                }}
                className="font-bold text-primary underline-offset-2 hover:underline"
              >
                {isRegistering ? 'Sign In' : 'Sign Up'}
              </button>
            </p>
          </form>
        </div>
      </div>

      <aside className="login-stage order-1 relative flex w-full flex-col items-center justify-center overflow-hidden px-6 pb-4 pt-6 lg:order-2 lg:w-1/2 lg:px-10 lg:py-12" aria-label="Welcome illustration">
        <div className="login-grid" aria-hidden="true" />

        <div className="relative z-10 w-full max-w-[470px]">
          <div className="login-mascot">
            <OrbitScene mode={sceneMode} />
          </div>
        </div>

        <div className="relative z-10 mt-2 hidden text-center lg:block">
          <h2 className="text-2xl font-extrabold text-white">From requirements to architecture, in one workspace.</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-[#A8B9D3]">Specialised AI agents analyse your SRS, plan the work and design the system, so your team can move straight to building.</p>
          <ul className="mt-4 flex flex-wrap items-center justify-center gap-2" aria-label="Workflow stages">
            {['Requirements', 'Planning', 'Architecture', 'Development'].map((stage, index) => (
              <li key={stage} className="bt-chip">
                <span className="grid h-4 w-4 place-items-center rounded-full bg-[#3155D9] text-[10px] font-extrabold text-white">{index + 1}</span>
                {stage}
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  )
}

export default Login
