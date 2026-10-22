import { TYPE_STYLE } from '../diagramStyle'

// Colours for every kind of diagram node. Component types reuse the palette of the existing
// architecture diagram so the same component looks the same everywhere.
const EXTRA = {
  ACTOR: '#334155', SYSTEM: '#5B2DD8', INTERFACE: '#c026d3', TABLE: '#059669',
  CONTROLLER: '#2563eb', SERVICE: '#0891b2', REPOSITORY: '#059669', MODEL: '#d97706', MIDDLEWARE: '#7c3aed',
  CLIENT: '#64748b', UI_COMPONENT: '#5B2DD8', UTILITY: '#6b7280',
  GET: '#0891b2', POST: '#059669', PUT: '#d97706', PATCH: '#d97706', DELETE: '#dc2626',
  REQUEST: '#2563eb', RESPONSE: '#0891b2', DTO: '#6b7280',
  CLIENT_DEVICE: '#5B2DD8', SERVER: '#0891b2', CONTAINER: '#2563eb', MANAGED_SERVICE: '#7c3aed', CLOUD_SERVICE: '#64748b',
}

export const toneColor = (tone) => EXTRA[tone] || TYPE_STYLE[tone]?.color || '#6b7280'

export const EDGE_STYLE = {
  call: { color: '#8b86a8', width: 1.8, dash: undefined, end: 'arrow' },
  flow: { color: '#5B2DD8', width: 2.2, dash: undefined, end: 'arrow' },
  dep: { color: '#7c3aed', width: 1.4, dash: '5 3', end: 'arrow' },
  impl: { color: '#c026d3', width: 1.4, dash: '5 3', end: 'hollow' },
  fk: { color: '#059669', width: 1.6, dash: undefined, end: 'none' },
}

export const KIND_BADGE = {
  CLIENT_DEVICE: '💻', SERVER: '🖥', CONTAINER: '📦', MANAGED_SERVICE: '☁', CLOUD_SERVICE: '☁', OTHER: '▣',
}
