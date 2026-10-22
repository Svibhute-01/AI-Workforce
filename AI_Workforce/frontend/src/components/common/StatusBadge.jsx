function StatusBadge({ status }) {
  const getStatusStyles = (status) => {
    switch (status) {
      case 'Completed':
        return 'badge-success'
      case 'In Progress':
        return 'badge-info'
      case 'Todo':
        return 'badge-warning'
      case 'Planning':
        return 'bg-purple-100 text-primary'
      default:
        return 'bg-gray-100 text-text-secondary'
    }
  }

  return (
    <span className={`badge ${getStatusStyles(status)}`}>
      {status}
    </span>
  )
}

export default StatusBadge
