// Colours and labels shared by the overview and detailed architecture diagrams.
export const TYPE_STYLE = {
  FRONTEND: { color: '#5B4A1A', label: 'Frontend' },
  GATEWAY: { color: '#7C6A2B', label: 'Gateway' },
  API: { color: '#5B8FB9', label: 'API' },
  SERVICE: { color: '#3E9E8F', label: 'Service' },
  AI_SERVICE: { color: '#E0B83F', label: 'AI service' },
  QUEUE: { color: '#C9697A', label: 'Queue' },
  CACHE: { color: '#B65A8A', label: 'Cache' },
  DATABASE: { color: '#6E9A55', label: 'Database' },
  STORAGE: { color: '#8DB36A', label: 'Storage' },
  EXTERNAL_SYSTEM: { color: '#8C8672', label: 'External system' },
  OTHER: { color: '#8C8672', label: 'Other' },
}

export const styleFor = (type) => TYPE_STYLE[type] || TYPE_STYLE.OTHER

export const clip = (text, max) => {
  const value = String(text ?? '')
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}
