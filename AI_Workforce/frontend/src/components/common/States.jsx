import { AlertCircle, Inbox, RefreshCw, WifiOff } from 'lucide-react'
import { Link } from 'react-router-dom'

export function Skeleton({ className = '' }) {
  return <div className={`bt-skeleton ${className}`} aria-hidden="true" />
}

export function EmptyState({ icon: Icon = Inbox, title, hint, to, cta, children }) {
  return (
    <div className="bt-empty flex flex-col items-center justify-center px-4 py-10 text-center">
      <div className="bt-icon-bubble mb-3 h-12 w-12"><Icon className="h-5 w-5" /></div>
      <p className="text-sm font-bold text-text-primary">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-xs text-text-secondary">{hint}</p>}
      {to && <Link to={to} className="btn-primary mt-4 inline-block text-sm">{cta}</Link>}
      {children}
    </div>
  )
}

export function ErrorState({ title = "Couldn't load this page", message, onRetry, retrying = false }) {
  return (
    <div role="alert" className="card flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-4 rounded-full bg-red-50 p-4"><WifiOff className="h-7 w-7 text-red-500" /></div>
      <h2 className="text-lg font-extrabold text-text-primary">{title}</h2>
      {message && <p className="mt-1 max-w-md text-sm text-text-secondary">{message}</p>}
      {onRetry && (
        <button type="button" onClick={onRetry} disabled={retrying} className="btn-primary mt-5 flex items-center gap-2">
          <RefreshCw className={`h-4 w-4 ${retrying ? 'animate-spin' : ''}`} /> Try again
        </button>
      )}
    </div>
  )
}

export function Notice({ tone = 'error', children, onRetry, onDismiss }) {
  const style = tone === 'success' ? 'border-green-200 bg-green-50 text-green-800' : tone === 'warning' ? 'border-yellow-200 bg-yellow-50 text-yellow-800' : 'border-red-200 bg-red-50 text-red-700'
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`mb-6 flex items-center justify-between gap-3 rounded-xl border px-4 py-3 text-sm ${style}`}>
      <span className="flex items-center gap-2"><AlertCircle className="h-4 w-4 shrink-0" />{children}</span>
      <span className="flex shrink-0 items-center gap-3">
        {onRetry && <button type="button" onClick={onRetry} className="font-bold underline">Retry</button>}
        {onDismiss && <button type="button" onClick={onDismiss} className="font-bold underline">Dismiss</button>}
      </span>
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
      <div className="min-w-0">
        <h1 className="mb-1 text-3xl font-extrabold text-text-primary">{title}</h1>
        {subtitle && <p className="text-text-secondary">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  )
}
