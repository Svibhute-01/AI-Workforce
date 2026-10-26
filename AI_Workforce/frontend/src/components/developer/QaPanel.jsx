import { AlertCircle, CheckCircle, HelpCircle, Download, Loader2, Send, XCircle } from 'lucide-react'
import { canSendDefects, failedSteps, summaryLine, verdictInfo } from './qaUtils'

const TONE = {
  success: { text: 'text-ide-success', icon: CheckCircle },
  danger: { text: 'text-ide-danger', icon: XCircle },
  warn: { text: 'text-ide-warn', icon: HelpCircle },
  muted: { text: 'text-ide-muted', icon: HelpCircle },
}

const button =
  'flex items-center gap-1.5 px-2.5 py-1 rounded text-[13px] border border-ide-border text-ide-text2 hover:bg-ide-hover disabled:opacity-40 disabled:hover:bg-transparent'

function Evidence({ row }) {
  const steps = failedSteps(row)
  if (!steps.length) return null
  return (
    <details className="mt-1">
      <summary className="cursor-pointer text-xs text-ide-info">Evidence ({steps.length})</summary>
      <ul className="mt-1 space-y-2">
        {steps.map((step, index) => (
          <li key={index} className="text-xs border-l-2 border-ide-danger pl-3">
            <p className="font-mono text-ide-text">{step.request} <span className="text-ide-muted">answered {step.status ?? 'nothing'}</span></p>
            <ul className="list-disc pl-4 text-ide-dangertext">
              {step.failures.map((failure) => <li key={failure}>{failure}</li>)}
            </ul>
            {step.excerpt && <pre className="mt-1 font-mono text-ide-muted whitespace-pre-wrap break-all max-h-24 overflow-auto m-0">{step.excerpt}</pre>}
          </li>
        ))}
      </ul>
    </details>
  )
}

function QaPanel({ run, onSendDefects, sending, onExport, exporting }) {
  if (!run) {
    return <p className="text-[13px] text-ide-muted">Press the shield button on a task. QA starts the app, writes tests from the task's acceptance criteria, runs them over HTTP and gives a verdict for every criterion.</p>
  }
  const working = run.status === 'PROCESSING'
  const { tone } = verdictInfo(run.verdict)
  const Header = working ? Loader2 : TONE[tone].icon

  return (
    <div className="text-[13px]">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <Header className={`w-4 h-4 flex-shrink-0 ${working ? 'animate-spin text-ide-info' : TONE[tone].text}`} />
          <span className="font-medium text-ide-text truncate">QA: {run.task_id ? `${run.task_id} ` : ''}{run.task_title}</span>
        </div>
        <div className="flex items-center gap-2">
          {canSendDefects(run) && (
            <button onClick={onSendDefects} disabled={sending} className={button} title="Start the Developer AI again on this task with QA's failed criteria and evidence">
              <Send className="w-3.5 h-3.5" />{sending ? 'Sending...' : 'Send defects to Developer'}
            </button>
          )}
          <button onClick={onExport} disabled={exporting} className={button} title="Download all QA runs of this project as a CSV file">
            <Download className="w-3.5 h-3.5" />{exporting ? 'Exporting...' : 'Export QA runs'}
          </button>
        </div>
      </div>

      <p className={`mb-3 ${working ? 'text-ide-muted' : TONE[tone].text}`}>{summaryLine(run)}</p>

      {run.defects_sent && <p className="mb-3 text-ide-info">The defects were sent to the Developer AI. Run QA again once it has finished.</p>}
      {run.repaired > 0 && <p className="mb-3 text-ide-muted">QA repaired {run.repaired} of its own test(s) before judging the app.</p>}

      {run.blocked && (
        <div className="mb-3 bg-ide-danger/10 border border-ide-danger/40 text-ide-dangertext px-3 py-2 rounded flex gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div className="min-w-0">
            <p>{run.blocked}</p>
            {run.app_log && <pre className="mt-1 text-xs font-mono whitespace-pre-wrap max-h-32 overflow-auto m-0">{run.app_log}</pre>}
          </div>
        </div>
      )}
      {!run.blocked && run.status === 'FAILED' && run.errors?.length > 0 && (
        <p className="mb-3 text-ide-dangertext">{run.errors[0]}</p>
      )}

      {run.criteria?.length > 0 && (
        <ul className="space-y-2">
          {run.criteria.map((row) => {
            const info = verdictInfo(row.verdict)
            const Icon = TONE[info.tone].icon
            return (
              <li key={row.id} className="border border-ide-border rounded px-3 py-2">
                <div className="flex items-start gap-2">
                  <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${TONE[info.tone].text}`} />
                  <div className="min-w-0 flex-1">
                    <p className="text-ide-text"><span className="text-ide-muted">{row.id}</span> {row.text}</p>
                    <p className={`text-xs ${TONE[info.tone].text}`}>{info.label}: {row.reason}</p>
                    <Evidence row={row} />
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {run.log?.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-ide-muted">Progress log</summary>
          <ol className="mt-1 space-y-0.5 font-mono text-xs">
            {run.log.map((entry, index) => (
              <li key={index} className="flex gap-3 text-ide-text2">
                <span className="text-ide-faint flex-shrink-0">{new Date(entry.time).toLocaleTimeString()}</span>
                <span>{entry.message}</span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  )
}

export default QaPanel
