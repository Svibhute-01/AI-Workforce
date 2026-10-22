import { AlertCircle, CheckCircle, Loader2, XCircle } from 'lucide-react'

const STYLE = {
  PROCESSING: { icon: Loader2, color: 'text-status-info', label: 'Working', spin: true },
  COMPLETED: { icon: CheckCircle, color: 'text-status-success', label: 'Completed' },
  FAILED: { icon: XCircle, color: 'text-status-danger', label: 'Failed' },
}

function RunPanel({ run, onOpenFile }) {
  if (!run) {
    return <p className="text-sm text-text-secondary">Pick a task and press Implement. Progress shows up here while the agent works.</p>
  }
  const { icon: Icon, color, label, spin } = STYLE[run.status] || STYLE.FAILED

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className={`w-5 h-5 ${color} ${spin ? 'animate-spin' : ''}`} />
          <span className="font-medium text-text-primary">{run.task_id ? `${run.task_id}: ` : ''}{run.task_title || 'Developer run'}</span>
        </div>
        <span className={`text-sm font-medium ${color}`}>{label}{run.attempts ? ` · attempt ${run.attempts}` : ''}</span>
      </div>

      {run.summary && <p className="text-sm text-text-secondary mb-3">{run.summary}</p>}

      {run.status === 'FAILED' && run.errors?.length > 0 && (
        <div className="mb-3 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm flex gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <pre className="whitespace-pre-wrap break-words font-sans max-h-40 overflow-auto">{run.errors[0]}</pre>
        </div>
      )}

      {run.log?.length > 0 && (
        <ol className="space-y-1 mb-3">
          {run.log.map((entry, index) => (
            <li key={index} className="text-sm text-text-secondary flex gap-3">
              <span className="text-xs text-text-secondary/70 w-16 flex-shrink-0 pt-0.5">{new Date(entry.time).toLocaleTimeString()}</span>
              <span>{entry.message}</span>
            </li>
          ))}
        </ol>
      )}

      {run.changes?.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondary mb-1">Files changed</p>
          <ul className="space-y-1">
            {run.changes.map((change) => (
              <li key={`${change.action}-${change.path}`} className="text-sm flex items-center gap-2">
                <span className="text-xs px-1.5 py-0.5 rounded bg-primary-light text-primary">{change.action}</span>
                {change.action === 'delete'
                  ? <span className="text-text-secondary line-through">{change.path}</span>
                  : <button onClick={() => onOpenFile(change.path)} className="text-primary hover:underline truncate text-left">{change.path}</button>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default RunPanel
