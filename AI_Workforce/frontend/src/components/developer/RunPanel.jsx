import { AlertCircle, CheckCircle, Loader2, XCircle } from 'lucide-react'

const STYLE = {
  PROCESSING: { icon: Loader2, color: 'text-ide-info', label: 'Working', spin: true },
  COMPLETED: { icon: CheckCircle, color: 'text-ide-success', label: 'Completed' },
  FAILED: { icon: XCircle, color: 'text-ide-danger', label: 'Failed' },
}

function RunPanel({ run, onOpenFile }) {
  if (!run) {
    return <p className="text-[13px] text-ide-muted">Press Run on a task. Progress shows up here while the agent works.</p>
  }
  const { icon: Icon, color, label, spin } = STYLE[run.status] || STYLE.FAILED

  return (
    <div className="text-[13px]">
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className={`w-4 h-4 flex-shrink-0 ${color} ${spin ? 'animate-spin' : ''}`} />
          <span className="font-medium text-ide-text truncate">{run.task_id ? `${run.task_id}: ` : ''}{run.task_title || 'Developer run'}</span>
        </div>
        <span className={`font-medium flex-shrink-0 ${color}`}>{label}{run.attempts ? ` · attempt ${run.attempts}` : ''}</span>
      </div>

      {run.summary && <p className="text-ide-muted mb-3">{run.summary}</p>}

      {run.status === 'FAILED' && run.errors?.length > 0 && (
        <div className="mb-3 bg-ide-danger/10 border border-ide-danger/40 text-ide-dangertext px-3 py-2 rounded flex gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <pre className="whitespace-pre-wrap break-words font-mono text-xs max-h-40 overflow-auto">{run.errors[0]}</pre>
        </div>
      )}

      {run.log?.length > 0 && (
        <ol className="space-y-1 mb-3 font-mono text-xs">
          {run.log.map((entry, index) => (
            <li key={index} className="flex gap-3 text-ide-text2">
              <span className="text-ide-faint flex-shrink-0">{new Date(entry.time).toLocaleTimeString()}</span>
              <span>{entry.message}</span>
            </li>
          ))}
        </ol>
      )}

      {run.changes?.length > 0 && (
        <div>
          <p className="text-[11px] uppercase tracking-wide text-ide-muted mb-1">Files changed ({run.changes.length})</p>
          <ul className="grid grid-cols-1 xl:grid-cols-2 gap-x-6 gap-y-0.5">
            {run.changes.map((change) => (
              <li key={`${change.action}-${change.path}`} className="flex items-center gap-2 min-w-0">
                <span className="text-[10px] px-1.5 rounded bg-ide-hover text-ide-muted flex-shrink-0">{change.action}</span>
                {change.action === 'delete'
                  ? <span className="text-ide-muted line-through truncate">{change.path}</span>
                  : <button onClick={() => onOpenFile(change.path)} className="text-ide-info hover:underline truncate text-left">{change.path}</button>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default RunPanel
