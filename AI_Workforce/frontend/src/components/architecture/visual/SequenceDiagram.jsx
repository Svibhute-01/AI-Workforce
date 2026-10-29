import { useMemo, useState } from 'react'
import DiagramCanvas, { useCanvas } from './DiagramCanvas'
import { clip } from './diagramModels'
import { toneColor } from './visualTheme'

/**
 * Sequence diagram from a sequence model: lifelines for the participants, numbered messages in
 * order. Used for the high-level sequence (components of one data flow) and the detailed sequence
 * (LLD participants and the API behind each call).
 */

const HEAD_W = 176
const HEAD_H = 58
const GAP = 218
const MARGIN = 30
const ROW = 66
const MONO = 'ui-monospace, Menlo, Consolas, monospace'

const wrap = (text, chars) => {
  const words = String(text || '').split(/\s+/).filter(Boolean)
  const lines = []
  let line = ''
  words.forEach((word) => {
    if ((line + ' ' + word).trim().length > chars && line) { lines.push(line); line = word } else line = `${line} ${word}`.trim()
  })
  if (line) lines.push(line)
  if (lines.length > 2) return [lines[0], clip(lines.slice(1).join(' '), chars)]
  return lines
}

function Sequence({ model, selected, highlightIds, onSelect }) {
  const canvas = useCanvas()
  const [hover, setHover] = useState(null)
  const xOf = useMemo(() => Object.fromEntries(model.participants.map((p, i) => [p.id, MARGIN + HEAD_W / 2 + i * GAP])), [model])
  const top = HEAD_H + 46
  const bottom = top + model.messages.length * ROW + 10
  const selectedKey = selected ? `${selected.type}:${selected.id}` : null
  const select = (ref) => { if (ref && !canvas.wasDragged()) onSelect?.(ref) }

  return (
    <g>
      <defs>
        <marker id="seq-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#5B4A1A" />
        </marker>
      </defs>

      {model.participants.map((p) => {
        const x = xOf[p.id]
        const c = toneColor(p.tone)
        const key = p.ref ? `${p.ref.type}:${p.ref.id}` : null
        const isSelected = key && key === selectedKey
        const marked = key && highlightIds?.has(key)
        const faded = hover && hover !== p.id && !model.messages.some((m) => (m.from === hover || m.to === hover) && (m.from === p.id || m.to === p.id))
        return (
          <g key={p.id} data-participant={p.id} opacity={faded ? 0.35 : 1} style={{ cursor: p.ref ? 'pointer' : 'default' }}
            onMouseEnter={() => setHover(p.id)} onMouseLeave={() => setHover(null)} onClick={() => select(p.ref)}>
            <title>{`${p.label} — ${p.sublabel}`}</title>
            <line x1={x} y1={HEAD_H} x2={x} y2={bottom} stroke={c} strokeOpacity="0.45" strokeWidth="1.6" strokeDasharray="5 5" />
            {(isSelected || marked) && <rect x={x - HEAD_W / 2 - 5} y={-5} width={HEAD_W + 10} height={HEAD_H + 10} rx="13" fill="none" stroke={isSelected ? '#5B4A1A' : '#B65A8A'} strokeWidth="2.6" strokeDasharray={isSelected ? undefined : '5 3'} />}
            <rect x={x - HEAD_W / 2} y="0" width={HEAD_W} height={HEAD_H} rx="9" fill="#FFF9DF" stroke={c} strokeWidth="2" />
            <rect x={x - HEAD_W / 2} y="0" width="7" height={HEAD_H} rx="3" fill={c} />
            {p.kind === 'actor' && <g stroke={c} strokeWidth="1.6" fill="none"><circle cx={x - HEAD_W / 2 + 22} cy="18" r="5" /><path d={`M ${x - HEAD_W / 2 + 22} 23 v 12 M ${x - HEAD_W / 2 + 14} 28 h 16 M ${x - HEAD_W / 2 + 22} 35 l -6 9 M ${x - HEAD_W / 2 + 22} 35 l 6 9`} strokeLinecap="round" /></g>}
            <text x={x + (p.kind === 'actor' ? 10 : 6)} y="24" fontSize="12.5" fontWeight="700" textAnchor="middle" fill="#34312B">{clip(p.label, 20)}</text>
            <text x={x + (p.kind === 'actor' ? 10 : 6)} y="42" fontSize="10" textAnchor="middle" fill="#6F6446">{clip(p.sublabel, 26)}</text>
          </g>
        )
      })}

      {model.messages.map((m, i) => {
        const y = top + i * ROW + ROW / 2
        const fx = xOf[m.from]
        const tx = xOf[m.to]
        if (fx === undefined || tx === undefined) return null
        const live = !hover || m.from === hover || m.to === hover
        const lines = wrap(m.label, Math.max(18, Math.floor((Math.abs(tx - fx) || 190) / 6.3)))
        const self = m.from === m.to
        const dir = tx >= fx ? 1 : -1
        const x1 = fx + (self ? 0 : 6 * dir)
        const x2 = tx - (self ? 0 : 6 * dir)
        const mid = (fx + tx) / 2
        const badge = m.order > 0 ? String(m.order) : '▶'
        return (
          <g key={m.id} data-message={m.id} opacity={live ? 1 : 0.2}>
            <title>{m.tooltip || m.label}</title>
            {self ? (
              <path d={`M ${fx + 4} ${y - 10} h 42 v 22 h -38`} fill="none" stroke="#5B4A1A" strokeWidth="1.8" markerEnd="url(#seq-arrow)" />
            ) : (
              <line x1={x1} y1={y} x2={x2} y2={y} stroke="#5B4A1A" strokeWidth="1.9" markerEnd="url(#seq-arrow)" />
            )}
            <circle cx={fx + (self ? 4 : 18 * dir)} cy={y} r="0" />
            {lines.map((line, k) => (
              <text key={k} x={self ? fx + 54 : mid} y={y - 8 - (lines.length - 1 - k) * 13} fontSize="11" textAnchor={self ? 'start' : 'middle'} fill="#34312B">{k === 0 ? `${badge}. ${line}` : line}</text>
            ))}
            {m.detail && <text x={self ? fx + 54 : mid} y={y + 17} fontSize="10" fontFamily={MONO} textAnchor={self ? 'start' : 'middle'} fill="#5B8FB9">{clip(m.detail, 40)}</text>}
          </g>
        )
      })}
    </g>
  )
}

function SequenceDiagram({ model, selected, highlightIds, onSelect, label, resetKey }) {
  const width = MARGIN * 2 + HEAD_W + Math.max(model.participants.length - 1, 0) * GAP
  const height = HEAD_H + 46 + model.messages.length * ROW + 40
  return (
    <DiagramCanvas width={width} height={height} label={label} resetKey={resetKey}>
      <g transform={`translate(0 ${MARGIN / 2})`}>
        <Sequence model={model} selected={selected} highlightIds={highlightIds} onSelect={onSelect} />
      </g>
    </DiagramCanvas>
  )
}

export default SequenceDiagram
