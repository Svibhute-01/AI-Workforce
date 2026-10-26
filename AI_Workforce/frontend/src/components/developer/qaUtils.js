// Small helpers for showing QA results. Kept free of React so they can be tested directly.

const VERDICTS = {
  PASS: { label: 'Pass', tone: 'success' },
  FAIL: { label: 'Fail', tone: 'danger' },
  UNVERIFIED: { label: 'Not verified', tone: 'warn' },
  INCONCLUSIVE: { label: 'Inconclusive', tone: 'warn' },
  BLOCKED: { label: 'Blocked', tone: 'danger' },
}

export function verdictInfo(verdict) {
  return VERDICTS[verdict] || { label: verdict || 'Pending', tone: 'muted' }
}

// The newest run of each task. Runs arrive newest first, but do not rely on it.
export function latestByTask(runs) {
  const latest = {}
  for (const run of [...runs].sort((a, b) => b.id - a.id)) {
    if (run.task_id && !latest[run.task_id]) latest[run.task_id] = run
  }
  return latest
}

// One line for the run header: "FAIL · 1 of 2 criteria passed · 100% verified".
export function summaryLine(run) {
  if (!run) return ''
  if (run.status === 'PROCESSING') return 'QA is testing the running app...'
  const counts = run.counts || {}
  const passed = counts.PASS || 0
  const failed = counts.FAIL || 0
  const unverified = counts.UNVERIFIED || 0
  const parts = [verdictInfo(run.verdict).label.toUpperCase(), `${passed} of ${run.total || 0} criteria passed`]
  if (failed) parts.push(`${failed} failed`)
  if (unverified) parts.push(`${unverified} not verified`)
  parts.push(`${run.coverage ?? 0}% verified`)
  return parts.join(' · ')
}

// The steps of a criterion that did not pass, with what the app answered.
export function failedSteps(row) {
  const steps = []
  for (const scenario of row.scenarios || []) {
    for (const step of scenario.steps || []) {
      if (step.failures && step.failures.length) steps.push(step)
    }
  }
  return steps
}

export function canSendDefects(run) {
  return Boolean(run && run.status === 'COMPLETED' && run.verdict === 'FAIL' && !run.defects_sent)
}
