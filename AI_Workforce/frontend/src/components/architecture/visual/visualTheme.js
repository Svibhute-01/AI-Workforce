import { TYPE_STYLE } from '../diagramStyle'

// Colours for every kind of diagram node. Component types reuse the palette of the existing
// architecture diagram so the same component looks the same everywhere.
const EXTRA = {
  ACTOR: '#5B4A1A', SYSTEM: '#5B4A1A', INTERFACE: '#E0B83F', TABLE: '#6E9A55',
  CONTROLLER: '#5B8FB9', SERVICE: '#3E9E8F', REPOSITORY: '#6E9A55', MODEL: '#C9697A', MIDDLEWARE: '#7C6A2B',
  CLIENT: '#8C8672', UI_COMPONENT: '#5B4A1A', UTILITY: '#8C8672',
  GET: '#3E9E8F', POST: '#6E9A55', PUT: '#C9697A', PATCH: '#C9697A', DELETE: '#C0463E',
  REQUEST: '#5B8FB9', RESPONSE: '#3E9E8F', DTO: '#8C8672',
  CLIENT_DEVICE: '#5B4A1A', SERVER: '#3E9E8F', CONTAINER: '#5B8FB9', MANAGED_SERVICE: '#7C6A2B', CLOUD_SERVICE: '#8C8672',
}

export const toneColor = (tone) => EXTRA[tone] || TYPE_STYLE[tone]?.color || '#8C8672'

export const EDGE_STYLE = {
  call: { color: '#8C7A3F', width: 1.8, dash: undefined, end: 'arrow' },
  flow: { color: '#5B4A1A', width: 2.2, dash: undefined, end: 'arrow' },
  dep: { color: '#7C6A2B', width: 1.4, dash: '5 3', end: 'arrow' },
  impl: { color: '#E0B83F', width: 1.4, dash: '5 3', end: 'hollow' },
  fk: { color: '#6E9A55', width: 1.6, dash: undefined, end: 'none' },
}

export const KIND_BADGE = {
  CLIENT_DEVICE: '💻', SERVER: '🖥', CONTAINER: '📦', MANAGED_SERVICE: '☁', CLOUD_SERVICE: '☁', OTHER: '▣',
}
