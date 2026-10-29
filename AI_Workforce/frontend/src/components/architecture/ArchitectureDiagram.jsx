import { useMemo, useState } from 'react'
import DetailedArchitectureDiagram from './DetailedArchitectureDiagram'
import { clip, styleFor } from './diagramStyle'

/**
 * Draws the architecture diagram from `diagram.nodes` / `diagram.edges`, which the backend
 * derives from the validated components and relationships. Nothing here is hard-coded:
 * a node's column comes from its `layer`, its colour from its component type, and every
 * arrow is a real relationship.
 */

const NODE_W = 188
const NODE_H = 62
const COL_GAP = 120
const ROW_GAP = 30
const PAD = 24
const ARC_BASE = 46
const ARC_STEP = 22


function layout(nodes, edges) {
  const layers = [...new Set(nodes.map((n) => n.layer))].sort((a, b) => a - b)
  const column = Object.fromEntries(layers.map((layer, index) => [layer, index]))
  const rows = {}
  const positions = {}
  nodes.forEach((node) => {
    const col = column[node.layer]
    rows[col] = (rows[col] || 0) + 1
    positions[node.id] = { x: PAD + col * (NODE_W + COL_GAP), row: rows[col] - 1, col }
  })

  // An arrow that skips a column would run through the boxes in between, so it arcs above
  // them instead. Each such arrow gets its own height so several arcs do not overlap.
  const lifts = {}
  let skipping = 0
  edges.forEach((edge) => {
    const a = positions[edge.source]
    const b = positions[edge.target]
    if (a && b && Math.abs(a.col - b.col) > 1) lifts[edge.id] = ARC_BASE + ARC_STEP * skipping++
  })
  const topExtra = skipping ? ARC_BASE + ARC_STEP * (skipping - 1) + 16 : 0

  const tallest = Math.max(...Object.values(rows), 1)
  const height = PAD * 2 + tallest * NODE_H + (tallest - 1) * ROW_GAP + 18 + topExtra
  Object.keys(positions).forEach((id) => {
    const col = positions[id].col
    const colHeight = rows[col] * NODE_H + (rows[col] - 1) * ROW_GAP
    positions[id].y = topExtra + (height - topExtra - colHeight) / 2 + positions[id].row * (NODE_H + ROW_GAP)
  })
  const width = PAD * 2 + layers.length * NODE_W + (layers.length - 1) * COL_GAP
  return { positions, lifts, width, height }
}

function edgePath(source, target, lift) {
  const sy = source.y + NODE_H / 2
  const ty = target.y + NODE_H / 2
  if (lift) {
    // Skips a column: leave from the top of the source box and arc over the boxes in between.
    const sx = source.x + NODE_W / 2
    const tx = target.x + NODE_W / 2
    const top = Math.min(source.y, target.y) - lift
    return {
      d: `M ${sx} ${source.y} C ${sx} ${top}, ${tx} ${top}, ${tx} ${target.y}`,
      lx: (sx + tx) / 2,
      ly: 0.75 * top + 0.125 * (source.y + target.y), // the curve's midpoint
    }
  }
  if (source.col < target.col) {
    const sx = source.x + NODE_W
    const mid = (sx + target.x) / 2
    return { d: `M ${sx} ${sy} C ${mid} ${sy}, ${mid} ${ty}, ${target.x} ${ty}`, lx: mid, ly: (sy + ty) / 2 }
  }
  if (source.col > target.col) {
    const sx = source.x
    const tx = target.x + NODE_W
    const mid = (sx + tx) / 2
    return { d: `M ${sx} ${sy} C ${mid} ${sy}, ${mid} ${ty}, ${tx} ${ty}`, lx: mid, ly: (sy + ty) / 2 }
  }
  // Same column: loop out on the right-hand side.
  const x = source.x + NODE_W
  const bulge = x + 54
  return { d: `M ${x} ${sy} C ${bulge} ${sy}, ${bulge} ${ty}, ${x} ${ty}`, lx: bulge - 8, ly: (sy + ty) / 2 }
}

function OverviewDiagram({ diagram }) {
  const [showSource, setShowSource] = useState(false)
  const nodes = diagram?.nodes || []
  const edges = diagram?.edges || []
  const geometry = useMemo(() => (nodes.length ? layout(nodes, edges) : null), [nodes, edges])

  if (!geometry) return <p className="text-sm text-text-secondary">No diagram available.</p>

  const { positions, lifts, width, height } = geometry
  const usedTypes = [...new Set(nodes.map((n) => n.type))]
  const drawn = edges.filter((e) => positions[e.source] && positions[e.target])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-xs text-text-secondary">
        {usedTypes.map((type) => (
          <span key={type} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ background: styleFor(type).color }} />
            {styleFor(type).label}
          </span>
        ))}
        <span className="flex items-center gap-1.5"><span className="w-5 border-t-2 border-dashed border-gray-400" /> assumed / inferred</span>
      </div>

      <div className="overflow-x-auto border border-border-light rounded-lg bg-bg-light">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          width={Math.max(width, 480)}
          height={height}
          role="img"
          aria-label="System architecture diagram"
          className="mx-auto block"
        >
          <defs>
            <marker id="arch-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#8C7A3F" />
            </marker>
          </defs>

          {drawn.map((edge) => {
            const { d, lx, ly } = edgePath(positions[edge.source], positions[edge.target], lifts[edge.id])
            const label = clip(String(edge.interaction || edge.label || '').replace(/_/g, ' '), 14)
            return (
              <g key={edge.id}>
                <title>{edge.label}</title>
                <path d={d} fill="none" stroke="#8C7A3F" strokeWidth="1.6" markerEnd="url(#arch-arrow)" />
                <rect x={lx - label.length * 3.1 - 5} y={ly - 9} width={label.length * 6.2 + 10} height="17" rx="4" fill="#FFF9DF" stroke="#E9C65E" />
                <text x={lx} y={ly + 3.5} textAnchor="middle" fontSize="10" fill="#5C5338">{label}</text>
              </g>
            )
          })}

          {nodes.map((node) => {
            const { x, y } = positions[node.id]
            const { color } = styleFor(node.type)
            const certain = node.grounding === 'EXPLICIT'
            return (
              <g key={node.id}>
                <title>{`${node.label} (${node.type}, ${node.grounding})`}</title>
                <rect x={x} y={y} width={NODE_W} height={NODE_H} rx="10" fill="#FFF9DF" stroke={color} strokeWidth="2" strokeDasharray={certain ? undefined : '6 4'} />
                <rect x={x} y={y} width="7" height={NODE_H} rx="3" fill={color} />
                <text x={x + 20} y={y + 26} fontSize="13" fontWeight="600" fill="#34312B">{clip(node.label, 22)}</text>
                <text x={x + 20} y={y + 45} fontSize="10.5" fill="#6F6446">{node.id} · {styleFor(node.type).label}</text>
              </g>
            )
          })}
        </svg>
      </div>

      {!!drawn.length && (
        <p className="text-xs text-text-secondary">{nodes.length} components, {drawn.length} relationships. Hover a box or arrow for details.</p>
      )}

      {diagram?.mermaid && (
        <div>
          <button onClick={() => setShowSource((value) => !value)} className="text-xs font-medium text-primary hover:text-primary-dark">
            {showSource ? 'Hide' : 'Show'} Mermaid source
          </button>
          {showSource && (
            <pre className="mt-2 text-xs bg-bg-light text-text-primary rounded-lg p-3 overflow-x-auto">{diagram.mermaid}</pre>
          )}
        </div>
      )}
    </div>
  )
}

const VIEWS = [
  { key: 'detailed', label: 'Detailed' },
  { key: 'overview', label: 'Overview' },
]

/** Detailed view (components with their modules, endpoints and tables) by default, plus the simple overview. */
function ArchitectureDiagram({ diagram }) {
  const hasDetailed = Boolean(diagram?.detailed?.containers?.length)
  const [view, setView] = useState('detailed')
  const active = hasDetailed ? view : 'overview'

  return (
    <div className="space-y-4">
      {hasDetailed && (
        <div className="inline-flex rounded-lg border border-border-light overflow-hidden" role="group" aria-label="Diagram view">
          {VIEWS.map((item) => (
            <button
              key={item.key}
              onClick={() => setView(item.key)}
              aria-pressed={active === item.key}
              className={`px-4 py-1.5 text-sm font-medium transition-colors ${active === item.key ? 'bg-primary text-white' : 'bg-white text-text-secondary hover:bg-bg-light'}`}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
      {active === 'detailed' ? <DetailedArchitectureDiagram detailed={diagram.detailed} /> : <OverviewDiagram diagram={diagram} />}
    </div>
  )
}

export default ArchitectureDiagram
