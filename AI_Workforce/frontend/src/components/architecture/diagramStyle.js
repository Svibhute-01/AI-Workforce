// Colours and labels shared by the overview and detailed architecture diagrams.
export const TYPE_STYLE = {
  FRONTEND: { color: '#5B2DD8', label: 'Frontend' },
  GATEWAY: { color: '#7c3aed', label: 'Gateway' },
  API: { color: '#2563eb', label: 'API' },
  SERVICE: { color: '#0891b2', label: 'Service' },
  AI_SERVICE: { color: '#c026d3', label: 'AI service' },
  QUEUE: { color: '#d97706', label: 'Queue' },
  CACHE: { color: '#ea580c', label: 'Cache' },
  DATABASE: { color: '#059669', label: 'Database' },
  STORAGE: { color: '#16a34a', label: 'Storage' },
  EXTERNAL_SYSTEM: { color: '#64748b', label: 'External system' },
  OTHER: { color: '#6b7280', label: 'Other' },
}

export const styleFor = (type) => TYPE_STYLE[type] || TYPE_STYLE.OTHER

export const clip = (text, max) => {
  const value = String(text ?? '')
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}
