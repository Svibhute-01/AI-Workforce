const STYLES = {
  completed: 'badge-success',
  done: 'badge-success',
  'in progress': 'badge-info',
  in_progress: 'badge-info',
  processing: 'badge-info',
  todo: 'badge-warning',
  'to do': 'badge-warning',
  failed: 'badge-danger',
  overdue: 'badge-danger',
  planning: 'bg-purple-100 text-primary',
}

const LABELS = { TODO: 'To do', IN_PROGRESS: 'In progress', COMPLETED: 'Completed' }

function StatusBadge({ status }) {
  const key = String(status ?? '').toLowerCase()
  const style = STYLES[key] || 'bg-gray-100 text-text-secondary'

  return (
    <span className={`badge ${style}`}>
      {LABELS[status] || status || '—'}
    </span>
  )
}

export default StatusBadge
