import { useMemo, useState } from 'react'
import { clip, styleFor } from './diagramStyle'

/**
 * Detailed architecture diagram. Every box and arrow comes from `diagram.detailed`, which the
 * backend derives from the validated design: each HLD component is drawn as a container that
 * holds the LLD modules placed in it, the endpoints each controller serves and the database
 * tables. Arrows are real component relationships, module dependencies and table relationships.
 * Nothing here is hard-coded.
 */

const CW = 252 // container width
const COL_GAP = 104
const PAD = 24
const GAP_Y = 28
const HEADER_H = 52
const SECTION_H = 24
const MOD_H = 34
const EP_H = 24
const TBL_H = 36
const ARC_BASE = 46
const ARC_STEP = 22
const ROW_RIGHT = 34 // space kept free on the right of every row for same-column arrows
const LANE_STEP = 6

const METHOD_COLOR = { GET: '#3E9E8F', POST: '#6E9A55', PUT: '#C9697A', PATCH: '#C9697A', DELETE: '#C0463E' }
const KIND_LABEL = {
  CONTROLLER: 'CTRL', SERVICE: 'SVC', REPOSITORY: 'REPO', MODEL: 'MODEL', MIDDLEWARE: 'MW',
  CLIENT: 'CLIENT', UI_COMPONENT: 'UI', UTILITY: 'UTIL', OTHER: 'MOD',
}
const CARDINALITY = { ONE_TO_ONE: '1:1', ONE_TO_MANY: '1:N', MANY_TO_MANY: 'N:N' }
const EDGE = {
  relationship: { color: '#8C7A3F', width: 1.8, dash: undefined, marker: 'darrow-rel' },
  module: { color: '#7C6A2B', width: 1.3, dash: '5 3', marker: 'darrow-mod' },
  table: { color: '#6E9A55', width: 1.5, dash: undefined, marker: 'darrow-tbl' },
}

function rowsFor(container) {
  const rows = []
  let y = HEADER_H + 6
  const section = (label) => { rows.push({ type: 'section', label, y }); y += SECTION_H }
  const endpoint = (data, indent) => { rows.push({ type: 'endpoint', id: data.id, data, y, h: EP_H, indent }); y += EP_H }

  if (container.modules.length) {
    section(`Modules (${container.modules.length})`)
    container.modules.forEach((module) => {
      rows.push({ type: 'module', id: module.id, data: module, y, h: MOD_H })
      y += MOD_H
      module.endpoints.forEach((data) => endpoint(data, true))
      y += 4
    })
  }
  if (container.endpoints.length) {
    section(`Endpoints (${container.endpoints.length})`)
    container.endpoints.forEach((data) => endpoint(data, false))
  }
  if (container.tables.length) {
    section(`Tables (${container.tables.length})`)
    container.tables.forEach((data) => { rows.push({ type: 'table', id: data.id, data, y, h: TBL_H }); y += TBL_H })
    y += 4
  }
  return { rows, height: rows.length ? y + 6 : HEADER_H + 10 }
}

function layout(containers, edges) {
  const sized = containers.map((container) => ({ ...container, ...rowsFor(container) }))
  const layers = [...new Set(sized.map((c) => c.layer))].sort((a, b) => a - b)
  const column = Object.fromEntries(layers.map((layer, index) => [layer, index]))
  const stacked = {}
  const boxes = {}
  sized.forEach((container) => {
    const col = column[container.layer]
    const top = stacked[col] || 0
    boxes[container.id] = { ...container, col, x: PAD + col * (CW + COL_GAP), top }
    stacked[col] = top + container.height + GAP_Y
  })

  // Relationships that skip a whole column arc over the boxes in between, each at its own height.
  const lifts = {}
  let skipping = 0
  edges.filter((edge) => edge.kind === 'relationship').forEach((edge) => {
    const a = boxes[edge.source]
    const b = boxes[edge.target]
    if (a && b && Math.abs(a.col - b.col) > 1) lifts[edge.id] = ARC_BASE + ARC_STEP * skipping++
  })
  const topExtra = skipping ? ARC_BASE + ARC_STEP * (skipping - 1) + 16 : 0

  const tallest = Math.max(...Object.values(stacked), GAP_Y) - GAP_Y
  Object.values(boxes).forEach((box) => { box.y = topExtra + PAD + box.top })

  // Row anchors let module and table arrows leave from the exact row they belong to.
  const anchors = {}
  const owner = {}
  Object.values(boxes).forEach((box) => {
    anchors[box.id] = { box, cy: box.y + HEADER_H / 2 }
    box.rows.forEach((row) => {
      if (row.type === 'module' || row.type === 'table') {
        anchors[row.id] = { box, cy: box.y + row.y + row.h / 2 }
        owner[row.id] = box.id
      }
    })
  })

  // Module and table arrows between two rows of the same column run in a vertical "lane" beside the
  // rows. Arrows whose spans overlap get different lanes so they never lie on top of each other.
  const lanes = {}
  const byColumn = {}
  edges.forEach((edge) => {
    const a = anchors[edge.source]
    const b = anchors[edge.target]
    if (edge.kind !== 'relationship' && a && b && a.box.col === b.box.col) {
      ;(byColumn[a.box.col] = byColumn[a.box.col] || []).push({ key: edge.key, from: Math.min(a.cy, b.cy), to: Math.max(a.cy, b.cy) })
    }
  })
  Object.values(byColumn).forEach((list) => {
    const laneEnds = []
    list.sort((x, y) => x.from - y.from || x.to - y.to).forEach((item) => {
      let lane = laneEnds.findIndex((end) => end < item.from - 2)
      if (lane === -1) lane = laneEnds.length
      laneEnds[lane] = item.to
      lanes[item.key] = lane
    })
  })

  const width = PAD * 2 + layers.length * CW + (layers.length - 1) * COL_GAP
  const height = topExtra + PAD * 2 + tallest
  return { boxes, anchors, owner, lifts, lanes, width, height, boxTop: topExtra + PAD }
}

function path(a, b, { lift, lane, bulge = 22, boxTop = 0 } = {}) {
  if (lift) {
    // Skips a column: leave the side of the source, run up the gap beside it, cross above every box
    // in a channel of its own, then come down the gap beside the target. It never crosses a box.
    const forward = a.box.col < b.box.col
    const lane = Math.round((lift - ARC_BASE) / ARC_STEP)
    const offset = 14 + 6 * lane
    const sx = forward ? a.box.x + CW : a.box.x
    const tx = forward ? b.box.x : b.box.x + CW
    const gx1 = sx + (forward ? offset : -offset)
    const gx2 = tx + (forward ? -offset : offset)
    const topY = boxTop - lift
    return {
      d: `M ${sx} ${a.cy} L ${gx1} ${a.cy} L ${gx1} ${topY} L ${gx2} ${topY} L ${gx2} ${b.cy} L ${tx} ${b.cy}`,
      lx: (gx1 + gx2) / 2,
      ly: topY,
    }
  }
  if (a.box.col !== b.box.col) {
    const forward = a.box.col < b.box.col
    const sx = forward ? a.box.x + CW : a.box.x
    const tx = forward ? b.box.x : b.box.x + CW
    const mid = (sx + tx) / 2
    return { d: `M ${sx} ${a.cy} C ${mid} ${a.cy}, ${mid} ${b.cy}, ${tx} ${b.cy}`, lx: mid, ly: (a.cy + b.cy) / 2 }
  }
  if (lane !== undefined) {
    // Row to row in one column: leave the row on its right, run down a lane, come back into the target row.
    const edgeX = a.box.x + CW - ROW_RIGHT
    const laneX = a.box === b.box ? edgeX + 8 + LANE_STEP * lane : a.box.x + CW + 14 + LANE_STEP * lane
    return {
      d: `M ${edgeX} ${a.cy} L ${laneX} ${a.cy} L ${laneX} ${b.cy} L ${edgeX + 1} ${b.cy}`,
      lx: laneX + 16,
      ly: (a.cy + b.cy) / 2,
    }
  }
  // Same column, box to box: loop out on the right-hand side.
  const x = a.box.x + CW
  const out = x + bulge
  return { d: `M ${x} ${a.cy} C ${out} ${a.cy}, ${out} ${b.cy}, ${x} ${b.cy}`, lx: out - 4, ly: (a.cy + b.cy) / 2 }
}

function Row({ row, box, hover, onHover }) {
  const x = box.x
  const y = box.y + row.y
  if (row.type === 'section') {
    return <text x={x + 14} y={y + 15} fontSize="10" fontWeight="700" fill="#8C7A3F" letterSpacing="0.6">{row.label.toUpperCase()}</text>
  }
  if (row.type === 'endpoint') {
    const inset = row.indent ? 34 : 14
    const { method, path: route, summary, auth_required: auth } = row.data
    // Size the path to the room left of the lock icon so a long route never runs into it.
    const textX = x + inset + 6 + method.length * 6.4 + 6
    const room = Math.max(8, Math.floor((x + CW - ROW_RIGHT - (auth ? 24 : 10) - textX) / 6.3))
    return (
      <g>
        <title>{`${method} ${route}${summary ? ` — ${summary}` : ''}${auth ? ' (auth required)' : ''}`}</title>
        <rect x={x + inset} y={y + 2} width={CW - inset - ROW_RIGHT} height={EP_H - 4} rx="5" fill="#FFF3BF" stroke="#F0D77A" />
        <text x={x + inset + 6} y={y + 16} fontSize="9.5" fontWeight="700" fill={METHOD_COLOR[method] || '#5C5338'}>{method}</text>
        <text x={textX} y={y + 16} fontSize="10.5" fill="#34312B" fontFamily="ui-monospace, Menlo, Consolas, monospace">
          {clip(route, room)}
        </text>
        {auth && <text x={x + CW - ROW_RIGHT - 6} y={y + 16} fontSize="10" textAnchor="end" fill="#8C7A3F">🔒</text>}
      </g>
    )
  }
  const active = hover === row.id
  const isModule = row.type === 'module'
  const { data } = row
  return (
    <g onMouseEnter={() => onHover(row.id)} onMouseLeave={() => onHover(box.id)} style={{ cursor: 'default' }}>
      <title>{isModule ? `${data.name} (${data.kind}) — ${data.description}` : `${data.name} — ${data.description}`}</title>
      <rect x={x + 10} y={y + 2} width={CW - 10 - ROW_RIGHT} height={row.h - 4} rx="7" fill={active ? '#FFEFA8' : '#FFF9DF'} stroke={active ? '#7C6A2B' : '#EDD36E'} />
      {isModule ? (
        <>
          <rect x={x + 16} y={y + 9} width="40" height="16" rx="4" fill="#FFE47C" />
          <text x={x + 36} y={y + 21} fontSize="9" fontWeight="700" textAnchor="middle" fill="#5B4A1A">{KIND_LABEL[data.kind] || 'MOD'}</text>
          <text x={x + 64} y={y + 21} fontSize="12" fontWeight="600" fill="#34312B">{clip(data.name, 17)}</text>
          {data.methods > 0 && <text x={x + CW - ROW_RIGHT - 6} y={y + 21} fontSize="9.5" textAnchor="end" fill="#8C7A3F">{data.methods}ƒ</text>}
        </>
      ) : (
        <>
          <text x={x + 18} y={y + 17} fontSize="12" fontWeight="600" fill="#34312B">{clip(data.name, 24)}</text>
          <text x={x + CW - ROW_RIGHT - 6} y={y + 17} fontSize="9.5" textAnchor="end" fill="#8C7A3F">{data.columns} cols</text>
          <text x={x + 18} y={y + 29} fontSize="9.5" fill="#6F6446">{data.primary_key.length ? `PK: ${clip(data.primary_key.join(', '), 30)}` : 'no primary key'}</text>
        </>
      )}
    </g>
  )
}

function DetailedArchitectureDiagram({ detailed }) {
  const [hover, setHover] = useState(null)
  const [fit, setFit] = useState(false)
  const containers = detailed?.containers || []
  const relationships = detailed?.relationships || []
  const moduleEdges = detailed?.module_edges || []
  const tableEdges = detailed?.table_edges || []

  const edges = useMemo(
    () => [
      ...relationships.map((edge) => ({ ...edge, key: `relationship-${edge.id}`, kind: 'relationship', label: String(edge.interaction || '').replace(/_/g, ' '), tip: edge.label })),
      ...moduleEdges.map((edge) => ({ ...edge, key: `module-${edge.id}`, kind: 'module', label: '', tip: `${edge.source} depends on ${edge.target}` })),
      ...tableEdges.map((edge) => ({
        ...edge,
        key: `table-${edge.id}`,
        kind: 'table',
        label: CARDINALITY[edge.cardinality] || '',
        tip: `${edge.source}.${edge.source_column} → ${edge.target}.${edge.target_column} (${String(edge.cardinality || '').replace(/_/g, ' ').toLowerCase()})`,
      })),
    ],
    [relationships, moduleEdges, tableEdges],
  )
  const geometry = useMemo(() => (containers.length ? layout(containers, edges) : null), [containers, edges])
  if (!geometry) return <p className="text-sm text-text-secondary">No detailed diagram available.</p>

  const { boxes, anchors, owner, lifts, lanes, width, height, boxTop } = geometry
  const drawn = edges.filter((edge) => anchors[edge.source] && anchors[edge.target])
  const routeOf = (edge) => ({
    lift: edge.kind === 'relationship' ? lifts[edge.id] : undefined,
    lane: edge.kind === 'relationship' ? undefined : lanes[edge.key],
    bulge: 30,
    boxTop,
  })

  const touches = (edge) =>
    !hover || [edge.source, edge.target, owner[edge.source], owner[edge.target]].includes(hover)

  const counts = {
    components: containers.filter((c) => c.id !== 'DATA_MODEL').length,
    modules: containers.reduce((sum, c) => sum + c.modules.length, 0),
    endpoints: containers.reduce((sum, c) => sum + c.endpoints.length + c.modules.reduce((n, m) => n + m.endpoints.length, 0), 0),
    tables: containers.reduce((sum, c) => sum + c.tables.length, 0),
  }
  const usedTypes = [...new Set(containers.map((c) => c.type))]

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-text-secondary">
        {usedTypes.map((type) => (
          <span key={type} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ background: styleFor(type).color }} />
            {styleFor(type).label}
          </span>
        ))}
        <span className="flex items-center gap-1.5"><span className="w-5 border-t-2" style={{ borderColor: EDGE.relationship.color }} /> component relationship</span>
        <span className="flex items-center gap-1.5"><span className="w-5 border-t-2 border-dashed" style={{ borderColor: EDGE.module.color }} /> module dependency</span>
        <span className="flex items-center gap-1.5"><span className="w-5 border-t-2" style={{ borderColor: EDGE.table.color }} /> table relationship</span>
        <button onClick={() => setFit((value) => !value)} className="ml-auto font-medium text-primary hover:text-primary-dark">
          {fit ? 'Actual size' : 'Fit to width'}
        </button>
      </div>

      <div className="overflow-x-auto border border-border-light rounded-lg bg-bg-light">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          width={fit ? '100%' : width}
          height={fit ? undefined : height}
          role="img"
          aria-label="Detailed system architecture diagram"
          className="mx-auto block"
          data-testid="detailed-diagram"
        >
          <defs>
            {Object.entries(EDGE).map(([kind, style]) => (
              <marker key={kind} id={style.marker} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill={style.color} />
              </marker>
            ))}
          </defs>

          {Object.values(boxes).map((box) => {
            const { color } = styleFor(box.type)
            const certain = box.grounding === 'EXPLICIT'
            const lit = hover === box.id
            return (
              <g key={box.id} data-container={box.id} onMouseEnter={() => setHover(box.id)} onMouseLeave={() => setHover(null)}>
                <title>{`${box.label} (${box.type}, ${box.grounding})`}</title>
                <rect x={box.x} y={box.y} width={CW} height={box.height} rx="12" fill={lit ? '#FFF6CF' : '#FFF9DF'} stroke={color} strokeWidth="2" strokeDasharray={certain ? undefined : '6 4'} />
                <rect x={box.x} y={box.y} width="7" height={box.height} rx="3" fill={color} />
                <text x={box.x + 20} y={box.y + 24} fontSize="13.5" fontWeight="700" fill="#34312B">{clip(box.label, 26)}</text>
                <text x={box.x + 20} y={box.y + 42} fontSize="10.5" fill="#6F6446">
                  {box.id === 'DATA_MODEL' ? styleFor(box.type).label : `${box.id} · ${styleFor(box.type).label}`}{box.technology ? ` · ${clip(box.technology, 22)}` : ''}
                </text>
                {box.rows.length > 0 && <line x1={box.x + 14} y1={box.y + HEADER_H - 2} x2={box.x + CW - 14} y2={box.y + HEADER_H - 2} stroke="#EFD97F" />}
                {box.rows.map((row, index) => <Row key={`${row.type}-${row.id || index}`} row={row} box={box} hover={hover} onHover={setHover} />)}
              </g>
            )
          })}

          {drawn.map((edge) => {
            const style = EDGE[edge.kind]
            const { d } = path(anchors[edge.source], anchors[edge.target], routeOf(edge))
            const live = touches(edge)
            return (
              <g key={edge.key} opacity={live ? 1 : 0.12} data-edge={edge.kind} pointerEvents="none">
                <path d={d} fill="none" stroke={style.color} strokeWidth={style.width} strokeDasharray={style.dash} strokeLinejoin="round" markerEnd={`url(#${style.marker})`} />
              </g>
            )
          })}

          {drawn.filter((edge) => edge.label).map((edge) => {
            const { lx, ly } = path(anchors[edge.source], anchors[edge.target], routeOf(edge))
            const label = clip(edge.label, 14)
            return (
              <g key={`label-${edge.key}`} opacity={touches(edge) ? 1 : 0.12}>
                <title>{edge.tip}</title>
                <rect x={lx - label.length * 3.1 - 5} y={ly - 9} width={label.length * 6.2 + 10} height="17" rx="4" fill="#FFF9DF" stroke={edge.kind === 'table' ? '#CFE3B4' : '#E9C65E'} />
                <text x={lx} y={ly + 3.5} textAnchor="middle" fontSize="10" fill="#5C5338">{label}</text>
              </g>
            )
          })}
        </svg>
      </div>

      <p className="text-xs text-text-secondary">
        {counts.components} components · {counts.modules} modules · {counts.endpoints} endpoints · {counts.tables} tables
        {' · '}{drawn.length} connections. Hover a component, module or table to highlight what it connects to.
      </p>
    </div>
  )
}

export default DetailedArchitectureDiagram
