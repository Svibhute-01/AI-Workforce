const TEXT_KEYS = ['answer', 'response', 'result', 'text', 'message', 'output']
const SOURCE_KEYS = ['sources', 'references', 'citations', 'source_references']

const sourceLabel = (item) => {
  if (typeof item === 'string') return item.trim() || null
  if (!item || typeof item !== 'object') return null
  const name = item.document || item.filename || item.title || item.source
  if (!name) return null
  const page = item.page ?? item.page_number
  return page != null ? `${name} · p.${page}` : String(name)
}

export function normalizeAnswer(payload) {
  if (typeof payload === 'string') return { text: payload.trim() || null, sources: [] }
  if (!payload || typeof payload !== 'object') return { text: null, sources: [] }
  const textKey = TEXT_KEYS.find((key) => typeof payload[key] === 'string' && payload[key].trim())
  const sourceKey = SOURCE_KEYS.find((key) => Array.isArray(payload[key]))
  const sources = sourceKey ? [...new Set(payload[sourceKey].map(sourceLabel).filter(Boolean))] : []
  return { text: textKey ? payload[textKey].trim() : null, sources }
}
