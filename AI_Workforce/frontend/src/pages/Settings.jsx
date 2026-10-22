import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  User, Lock, Palette, Sparkles, Bell, Shield, Plug, AlertTriangle, Sun, Moon, Monitor,
  Eye, EyeOff, LogOut, Github, Slack, ListChecks, RefreshCw, Loader2, CheckCircle2, XCircle,
} from 'lucide-react'
import apiService from '../services/api'
import { applyTheme, getStoredTheme } from '../utils/theme'

const SECTIONS = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'account', label: 'Account', icon: Lock },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'ai', label: 'AI Settings', icon: Sparkles },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'integrations', label: 'Integrations', icon: Plug },
  { id: 'danger', label: 'Danger Zone', icon: AlertTriangle },
]

const NOTIFICATION_OPTIONS = [
  { key: 'ai_task_completion', label: 'AI task completion', description: 'When an AI agent finishes analysing requirements or building a plan.' },
  { key: 'ai_agent_failure', label: 'AI agent failure', description: 'When an AI agent run fails and needs your attention.' },
  { key: 'project_updates', label: 'Project updates', description: 'Changes to projects you own, such as new documents.' },
  { key: 'task_updates', label: 'Task updates', description: 'Changes to tasks in your project plans.' },
]

const THEME_OPTIONS = [
  { value: 'light', label: 'Light', icon: Sun, hint: 'Bright interface' },
  { value: 'dark', label: 'Dark', icon: Moon, hint: 'Easier on the eyes' },
  { value: 'system', label: 'System', icon: Monitor, hint: 'Match your device' },
]

const formatDate = (value) =>
  value ? new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : null

function Skeleton({ className = '' }) {
  return <div className={`animate-pulse rounded-lg bg-gray-200 ${className}`} />
}

function Card({ title, description, children }) {
  return (
    <div className="card p-6">
      <h2 className="text-lg font-bold text-text-primary">{title}</h2>
      {description && <p className="text-sm text-text-secondary mt-1">{description}</p>}
      <div className="mt-6">{children}</div>
    </div>
  )
}

function InfoRow({ label, children }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 py-3 border-b border-border-light last:border-b-0">
      <span className="text-sm text-text-secondary">{label}</span>
      <span className="text-sm font-medium text-text-primary sm:text-right break-all">{children}</span>
    </div>
  )
}

function Toggle({ checked, onChange, disabled, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onChange}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-60 ${
        checked ? 'bg-primary' : 'bg-gray-400'
      }`}
    >
      <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  )
}

function InlineError({ message }) {
  if (!message) return null
  return (
    <div role="alert" className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
      <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  )
}

function PasswordField({ label, value, onChange, autoComplete }) {
  const [visible, setVisible] = useState(false)
  return (
    <div>
      <label className="block text-sm font-medium text-text-primary mb-2">{label}</label>
      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
          className="input-field pr-11"
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
        >
          {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  )
}

function Settings() {
  const navigate = useNavigate()
  const [active, setActive] = useState('profile')
  const [data, setData] = useState({ profile: null, preferences: null, ai: null, security: null, integrations: null })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)

  const [name, setName] = useState('')
  const [savingName, setSavingName] = useState(false)
  const [nameError, setNameError] = useState('')

  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' })
  const [savingPassword, setSavingPassword] = useState(false)
  const [passwordError, setPasswordError] = useState('')

  const [pendingKey, setPendingKey] = useState(null)

  const notify = useCallback((type, message) => {
    clearTimeout(toastTimer.current)
    setToast({ type, message })
    toastTimer.current = setTimeout(() => setToast(null), 3500)
  }, [])

  useEffect(() => () => clearTimeout(toastTimer.current), [])

  const load = useCallback(async () => {
    setLoading(true)
    const calls = {
      profile: apiService.settings.getProfile,
      preferences: apiService.settings.getPreferences,
      ai: apiService.settings.getAI,
      security: apiService.settings.getSecurity,
      integrations: apiService.settings.getIntegrations,
    }
    const keys = Object.keys(calls)
    const results = await Promise.allSettled(keys.map((key) => calls[key]()))
    const nextData = {}
    const nextErrors = {}
    results.forEach((result, index) => {
      nextData[keys[index]] = result.status === 'fulfilled' ? result.value : null
      if (result.status === 'rejected') nextErrors[keys[index]] = result.reason.message
    })
    setData(nextData)
    setErrors(nextErrors)
    if (nextData.profile) setName(nextData.profile.display_name)
    if (nextData.preferences) applyTheme(nextData.preferences.theme)
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  // ---- profile -------------------------------------------------------------
  const saveProfile = async (event) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) { setNameError('Name cannot be empty'); return }
    setSavingName(true)
    setNameError('')
    try {
      const saved = await apiService.settings.updateProfile({ display_name: trimmed })
      setData((current) => ({ ...current, profile: saved }))
      setName(saved.display_name)
      localStorage.setItem('userName', saved.display_name)
      window.dispatchEvent(new Event('userNameChanged'))
      notify('success', 'Profile updated')
    } catch (error) {
      setNameError(error.message)
      notify('error', 'Could not update profile')
    } finally {
      setSavingName(false)
    }
  }

  // ---- password ------------------------------------------------------------
  const savePassword = async (event) => {
    event.preventDefault()
    setPasswordError('')
    if (passwords.next.length < 8) { setPasswordError('New password must be at least 8 characters'); return }
    if (passwords.next !== passwords.confirm) { setPasswordError('New password and confirmation do not match'); return }
    setSavingPassword(true)
    try {
      await apiService.settings.changePassword({ current_password: passwords.current, new_password: passwords.next })
      setPasswords({ current: '', next: '', confirm: '' })
      const security = await apiService.settings.getSecurity().catch(() => null)
      if (security) setData((current) => ({ ...current, security }))
      notify('success', 'Password updated')
    } catch (error) {
      setPasswordError(error.message)
    } finally {
      setSavingPassword(false)
    }
  }

  // ---- preferences ---------------------------------------------------------
  const changeTheme = async (value) => {
    const previous = data.preferences.theme
    if (value === previous) return
    setData((current) => ({ ...current, preferences: { ...current.preferences, theme: value } }))
    applyTheme(value)
    setPendingKey('theme')
    try {
      const saved = await apiService.settings.updatePreferences({ theme: value })
      setData((current) => ({ ...current, preferences: saved }))
      notify('success', 'Appearance saved')
    } catch (error) {
      setData((current) => ({ ...current, preferences: { ...current.preferences, theme: previous } }))
      applyTheme(previous)
      notify('error', error.message)
    } finally {
      setPendingKey(null)
    }
  }

  const toggleNotification = async (key) => {
    const previous = data.preferences.notifications[key]
    const setValue = (value) =>
      setData((current) => ({
        ...current,
        preferences: { ...current.preferences, notifications: { ...current.preferences.notifications, [key]: value } },
      }))
    setValue(!previous)
    setPendingKey(key)
    try {
      const saved = await apiService.settings.updatePreferences({ notifications: { [key]: !previous } })
      setData((current) => ({ ...current, preferences: saved }))
      notify('success', 'Notification preference saved')
    } catch (error) {
      setValue(previous)
      notify('error', error.message)
    } finally {
      setPendingKey(null)
    }
  }

  // ---- logout (same behaviour as the top bar) ------------------------------
  const logout = () => {
    localStorage.removeItem('isAuthenticated')
    localStorage.removeItem('accessToken')
    localStorage.removeItem('userName')
    navigate('/login')
  }

  const unavailable = (key, children) =>
    errors[key] ? (
      <div className="space-y-3">
        <InlineError message={errors[key]} />
        <button onClick={load} className="btn-outline inline-flex items-center gap-2 text-sm">
          <RefreshCw className="w-4 h-4" /> Retry
        </button>
      </div>
    ) : children

  const renderSection = () => {
    if (loading) {
      return (
        <div className="card p-6 space-y-4" aria-busy="true" aria-label="Loading settings">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-72" />
          <Skeleton className="h-10 w-full mt-6" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-32" />
        </div>
      )
    }

    const profile = data.profile
    const prefs = data.preferences

    switch (active) {
      case 'profile':
        return (
          <Card title="Profile" description="Your name is shown across the application.">
            {unavailable('profile', profile && (
              <form onSubmit={saveProfile} className="space-y-6 max-w-xl">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-primary text-white flex items-center justify-center text-2xl font-bold">
                    {(name.trim() || profile.display_name).charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <p className="font-semibold text-text-primary">{profile.display_name}</p>
                    <p className="text-sm text-text-secondary">{profile.email}</p>
                  </div>
                </div>
                <div>
                  <label htmlFor="display-name" className="block text-sm font-medium text-text-primary mb-2">Full name</label>
                  <input id="display-name" type="text" value={name} maxLength={120}
                    onChange={(event) => { setName(event.target.value); setNameError('') }} className="input-field" />
                </div>
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-text-primary mb-2">Email</label>
                  <input id="email" type="email" value={profile.email} disabled className="input-field opacity-70 cursor-not-allowed" />
                  <p className="text-xs text-text-secondary mt-2">Your email is your sign-in and can't be changed here.</p>
                </div>
                <InlineError message={nameError} />
                <button type="submit" disabled={savingName || name.trim() === profile.display_name}
                  className="btn-primary inline-flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
                  {savingName && <Loader2 className="w-4 h-4 animate-spin" />}
                  {savingName ? 'Saving...' : 'Save changes'}
                </button>
              </form>
            ))}
          </Card>
        )

      case 'account':
        return (
          <div className="space-y-6">
            <Card title="Account information" description="Details about your account.">
              {unavailable('profile', profile && (
                <div>
                  <InfoRow label="Email">{profile.email}</InfoRow>
                  <InfoRow label="Member since">{formatDate(profile.created_at) || 'Unknown'}</InfoRow>
                  <InfoRow label="Projects">{profile.project_count}</InfoRow>
                </div>
              ))}
            </Card>
            <Card title="Change password" description="Use at least 8 characters. Your new password is stored hashed and is never shown.">
              <form onSubmit={savePassword} className="space-y-5 max-w-xl">
                <PasswordField label="Current password" value={passwords.current} autoComplete="current-password"
                  onChange={(value) => { setPasswords({ ...passwords, current: value }); setPasswordError('') }} />
                <PasswordField label="New password" value={passwords.next} autoComplete="new-password"
                  onChange={(value) => { setPasswords({ ...passwords, next: value }); setPasswordError('') }} />
                <PasswordField label="Confirm new password" value={passwords.confirm} autoComplete="new-password"
                  onChange={(value) => { setPasswords({ ...passwords, confirm: value }); setPasswordError('') }} />
                <InlineError message={passwordError} />
                <button type="submit" disabled={savingPassword || !passwords.current || !passwords.next || !passwords.confirm}
                  className="btn-primary inline-flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
                  {savingPassword && <Loader2 className="w-4 h-4 animate-spin" />}
                  {savingPassword ? 'Updating...' : 'Update password'}
                </button>
              </form>
            </Card>
          </div>
        )

      case 'appearance':
        return (
          <Card title="Appearance" description="Choose how the application looks. Your choice is saved to your account.">
            {unavailable('preferences', prefs && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl" role="radiogroup" aria-label="Theme">
                {THEME_OPTIONS.map(({ value, label, icon: Icon, hint }) => {
                  const selected = (prefs.theme || getStoredTheme()) === value
                  return (
                    <button key={value} type="button" role="radio" aria-checked={selected}
                      disabled={pendingKey === 'theme'} onClick={() => changeTheme(value)}
                      className={`text-left p-4 rounded-lg border-2 transition-all hover:-translate-y-0.5 hover:shadow-sm disabled:opacity-60 ${
                        selected ? 'border-primary bg-primary-light' : 'border-border-light'
                      }`}>
                      <div className="flex items-center justify-between mb-3">
                        <Icon className={`w-6 h-6 ${selected ? 'text-primary' : 'text-text-secondary'}`} />
                        {selected && <CheckCircle2 className="w-5 h-5 text-primary" />}
                      </div>
                      <p className="font-semibold text-text-primary">{label}</p>
                      <p className="text-xs text-text-secondary mt-1">{hint}</p>
                    </button>
                  )
                })}
              </div>
            ))}
          </Card>
        )

      case 'ai':
        return (
          <Card title="AI settings" description="The AI configuration this server is running with. It is managed by environment variables on the server.">
            {unavailable('ai', data.ai && (
              <div className="max-w-xl">
                <InfoRow label="Provider">{data.ai.provider}</InfoRow>
                <InfoRow label="Language model">{data.ai.model}</InfoRow>
                <InfoRow label="Embedding model">{data.ai.embedding_model}</InfoRow>
                <InfoRow label="Vector store">{data.ai.vector_store}</InfoRow>
                <InfoRow label="API key">
                  <span className={`badge ${data.ai.api_key_configured ? 'badge-success' : 'badge-danger'}`}>
                    {data.ai.api_key_configured ? 'Configured' : 'Not configured'}
                  </span>
                </InfoRow>
                <p className="text-xs text-text-secondary mt-4">API keys and secrets are never displayed or sent to the browser.</p>
              </div>
            ))}
          </Card>
        )

      case 'notifications':
        return (
          <Card title="Notifications" description="Choose which events matter to you.">
            {unavailable('preferences', prefs && (
              <div className="max-w-2xl">
                <div className="divide-y divide-border-light border border-border-light rounded-lg">
                  {NOTIFICATION_OPTIONS.map(({ key, label, description }) => (
                    <div key={key} className="flex items-center justify-between gap-4 p-4">
                      <div>
                        <p className="font-medium text-text-primary">{label}</p>
                        <p className="text-sm text-text-secondary">{description}</p>
                      </div>
                      <Toggle label={label} checked={!!prefs.notifications[key]}
                        disabled={pendingKey === key} onChange={() => toggleNotification(key)} />
                    </div>
                  ))}
                </div>
                <p className="text-xs text-text-secondary mt-4">
                  Your preferences are saved to your account. Email and in-app delivery isn't active yet, so no notifications are sent for now.
                </p>
              </div>
            ))}
          </Card>
        )

      case 'security':
        return (
          <Card title="Security" description="Basic information about how your account is protected.">
            {unavailable('security', data.security && (
              <div className="max-w-xl">
                <InfoRow label="Sign-in method">{data.security.auth_method}</InfoRow>
                <InfoRow label="Password storage">{data.security.password_storage}</InfoRow>
                <InfoRow label="Session length">{data.security.session_duration_hours} hours</InfoRow>
                <InfoRow label="Account created">{formatDate(data.security.account_created) || 'Unknown'}</InfoRow>
                <InfoRow label="Password last changed">
                  {formatDate(data.security.password_last_changed) || 'Not changed since sign-up'}
                </InfoRow>
                <div className="pt-6">
                  <button onClick={logout} className="btn-outline inline-flex items-center gap-2">
                    <LogOut className="w-4 h-4" /> Sign out
                  </button>
                  <p className="text-xs text-text-secondary mt-3">
                    Signing out removes your session from this browser. Sessions on other devices end when they expire.
                  </p>
                </div>
              </div>
            ))}
          </Card>
        )

      case 'integrations': {
        const icons = { github: Github, jira: ListChecks, slack: Slack }
        return (
          <Card title="Integrations" description="Connect the tools your team already uses.">
            {unavailable('integrations', data.integrations && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {data.integrations.map((item) => {
                  const Icon = icons[item.key] || Plug
                  return (
                    <div key={item.key} className="border border-border-light rounded-lg p-5 flex flex-col transition-shadow hover:shadow-md">
                      <div className="flex items-center justify-between mb-4">
                        <div className="bg-primary-light p-2.5 rounded-lg"><Icon className="w-5 h-5 text-primary" /></div>
                        <span className="badge bg-gray-100 text-text-secondary">
                          {item.status === 'connected' ? 'Connected' : 'Not connected'}
                        </span>
                      </div>
                      <h3 className="font-bold text-text-primary">{item.name}</h3>
                      <p className="text-sm text-text-secondary mt-1 flex-1">{item.description}</p>
                      <button disabled={!item.available}
                        className="btn-outline mt-5 text-sm disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:bg-transparent">
                        {item.available ? 'Connect' : 'Coming soon'}
                      </button>
                    </div>
                  )
                })}
              </div>
            ))}
          </Card>
        )
      }

      case 'danger':
        return (
          <div className="card p-6 border-red-200">
            <h2 className="text-lg font-bold text-red-700">Danger zone</h2>
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="font-medium text-red-800">Account and project deletion aren't available yet</p>
              <p className="text-sm text-red-700 mt-1">
                The backend doesn't support deleting accounts or projects, so no destructive actions are offered here.
                They will appear here, with a confirmation step, once they are supported.
              </p>
            </div>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">Settings</h1>
        <p className="text-text-secondary">Manage your profile, preferences and account security.</p>
      </div>

      {toast && (
        <div role="status" aria-live="polite"
          className={`fixed top-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium border ${
            toast.type === 'success' ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-700'
          }`}>
          {toast.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
          {toast.message}
        </div>
      )}

      <div className="flex flex-col md:flex-row gap-6">
        <nav aria-label="Settings sections" className="md:w-56 shrink-0">
          <ul className="flex md:flex-col gap-1 overflow-x-auto pb-2 md:pb-0">
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <li key={id}>
                <button onClick={() => setActive(id)} aria-current={active === id ? 'page' : undefined}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                    active === id
                      ? 'bg-primary-light text-primary'
                      : id === 'danger'
                        ? 'text-red-600 hover:bg-red-50'
                        : 'text-text-secondary hover:bg-gray-100 hover:text-text-primary'
                  }`}>
                  <Icon className="w-4 h-4" />
                  {label}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex-1 min-w-0">{renderSection()}</div>
      </div>
    </div>
  )
}

export default Settings
