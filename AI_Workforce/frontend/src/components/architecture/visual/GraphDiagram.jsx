import { useMemo, useState } from 'react'
import DiagramCanvas, { useCanvas } from './DiagramCanvas'
import { clip } from './diagramModels'
import { layoutCompound, routeEdges } from './graphLayout'
import { EDGE_STYLE, KIND_BADGE, toneColor } from './visualTheme'

/**
 * Draws a graph model from diagramModels.js: every node, arrow and boundary box is data. Shapes
 * differ by what the element is (actor, frontend, service, AI, database, external system, class,
 * table ...). Hovering highlights what an element connects to; clicking selects it.
 */

const MONO = 'ui-monospace, Menlo, Consolas, monospace'
const MARGIN = 28
const TAGS = {
  PK: { bg: '#fef3c7', fg: '#b45309' },
  FK: { bg: '#dbeafe', fg: '#1d4ed8' },
  UQ: { bg: '#f3f4f6', fg: '#4b5563' },
}
const tint = (color, alpha = '14') => `${color}${alpha}`
const fits = (width, size, mono = false) => Math.max(6, Math.floor(width / (size * (mono ? 0.64 : 0.58))))
const dashed = (node) => (node.grounding && node.grounding !== 'EXPLICIT' && node.ref?.type !== 'table' ? '6 4' : undefined)

function Tag({ text, x, y }) {
  const style = TAGS[text]
  if (!style) return <text x={x} y={y + 10} fontSize="10" fill="#8b86a8">{text}</text>
  return (
    <g>
      <rect x={x} y={y} width="22" height="13" rx="3" fill={style.bg} />
      <text x={x + 11} y={y + 10} fontSize="8.5" fontWeight="700" textAnchor="middle" fill={style.fg}>{text}</text>
    </g>
  )
}

function Rows({ rows, x, y, width, rowHeight = 17 }) {
  return rows.map((row, i) => {
    const top = y + i * rowHeight
    const tagged = Boolean(row.tag && TAGS[row.tag])
    const left = x + (tagged ? 28 : 0)
    const size = row.mono ? 10.5 : 11
    const right = row.right ? clip(row.right, 14) : ''
    const room = width - (tagged ? 28 : 0) - (right ? right.length * 5.4 + 10 : 0) - (row.tag && !tagged ? 18 : 0)
    return (
      <g key={`${i}-${row.text}`}>
        {tagged && <Tag text={row.tag} x={x} y={top + 1} />}
        <text x={left} y={top + 12} fontSize={size} fontFamily={row.mono ? MONO : undefined} fill={row.muted ? '#8b86a8' : '#333333'}>
          {clip(row.text, fits(room, size, row.mono))}
        </text>
        {right && <text x={x + width} y={top + 12} fontSize="9.5" textAnchor="end" fill="#8b86a8">{right}</text>}
        {row.tag && !tagged && <text x={x + width} y={top + 12} fontSize="10" textAnchor="end" fill="#8b86a8">{row.tag}</text>}
      </g>
    )
  })
}

function Title({ node, x, y, width, anchor = 'start', size = 13, subSize = 10.5 }) {
  const cx = anchor === 'middle' ? x + width / 2 : x
  return (
    <>
      <text x={cx} y={y} fontSize={size} fontWeight="700" textAnchor={anchor} fill="#1a1a1a">{clip(node.title, fits(width, size))}</text>
      {node.subtitle && <text x={cx} y={y + size + 3} fontSize={subSize} textAnchor={anchor} fill="#666666">{clip(node.subtitle, fits(width, subSize))}</text>}
    </>
  )
}

function Shape({ node, box }) {
  const { x, y, w, h } = box
  const c = toneColor(node.tone)
  const dash = dashed(node)
  const rows = node.rows || []
  const cx = x + w / 2
  const stroke = { stroke: c, strokeWidth: 2, strokeDasharray: dash, fill: '#ffffff' }

  switch (node.shape) {
    case 'actor':
      return (
        <g>
          <circle cx={cx} cy={y + 20} r="11" fill="#ffffff" stroke={c} strokeWidth="2.2" />
          <path d={`M ${cx} ${y + 31} L ${cx} ${y + 56} M ${cx - 17} ${y + 41} L ${cx + 17} ${y + 41} M ${cx} ${y + 56} L ${cx - 13} ${y + 74} M ${cx} ${y + 56} L ${cx + 13} ${y + 74}`} stroke={c} strokeWidth="2.2" fill="none" strokeLinecap="round" />
          <text x={cx} y={y + 91} fontSize="12.5" fontWeight="700" textAnchor="middle" fill="#1a1a1a">{clip(node.title, fits(w, 12.5))}</text>
        </g>
      )
    case 'system':
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} rx="16" {...stroke} strokeWidth="2.6" fill={tint(c, '10')} />
          <Title node={node} x={x} y={y + 30} width={w - 16} anchor="middle" size={15} subSize={11} />
          <Rows rows={rows} x={x + 22} y={y + 62} width={w - 44} />
        </g>
      )
    case 'frontend':
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} rx="10" {...stroke} />
          <path d={`M ${x} ${y + 18} L ${x} ${y + 10} Q ${x} ${y} ${x + 10} ${y} L ${x + w - 10} ${y} Q ${x + w} ${y} ${x + w} ${y + 10} L ${x + w} ${y + 18} Z`} fill={tint(c, '22')} />
          {[0, 1, 2].map((i) => <circle key={i} cx={x + 14 + i * 12} cy={y + 9} r="3" fill={c} opacity={0.55 - i * 0.12} />)}
          <Title node={node} x={x + 14} y={y + 38} width={w - 28} />
          <Rows rows={rows} x={x + 14} y={y + 62} width={w - 28} />
        </g>
      )
    case 'ai': {
      const inset = 24
      return (
        <g>
          <polygon points={`${x + inset},${y} ${x + w - inset},${y} ${x + w},${y + h / 2} ${x + w - inset},${y + h} ${x + inset},${y + h} ${x},${y + h / 2}`} {...stroke} fill={tint(c, '12')} />
          <Title node={node} x={x + inset} y={y + h / 2 - (rows.length ? 14 : 6)} width={w - inset * 2} anchor="middle" />
          <Rows rows={rows} x={x + inset + 6} y={y + h / 2 + 12} width={w - inset * 2 - 12} />
        </g>
      )
    }
    case 'database': case 'storage': case 'cache': {
      const ry = 10
      return (
        <g>
          <path d={`M ${x} ${y + ry} L ${x} ${y + h - ry} A ${w / 2} ${ry} 0 0 0 ${x + w} ${y + h - ry} L ${x + w} ${y + ry}`} {...stroke} fill={tint(c, '10')} />
          <ellipse cx={cx} cy={y + ry} rx={w / 2} ry={ry} {...stroke} fill={tint(c, '24')} />
          <Title node={node} x={x + 14} y={y + 38} width={w - 28} anchor="middle" />
          <Rows rows={rows} x={x + 18} y={y + 62} width={w - 36} />
        </g>
      )
    }
    case 'queue': {
      const skew = 16
      return (
        <g>
          <polygon points={`${x + skew},${y} ${x + w},${y} ${x + w - skew},${y + h} ${x},${y + h}`} {...stroke} fill={tint(c, '12')} />
          <Title node={node} x={x + skew} y={y + h / 2 - (rows.length ? 8 : 4)} width={w - skew * 2} anchor="middle" />
          <Rows rows={rows} x={x + skew + 8} y={y + h / 2 + 16} width={w - skew * 2 - 16} />
        </g>
      )
    }
    case 'cloud': {
      const p = (fx, fy) => `${x + fx * w} ${y + fy * h}`
      const d = `M ${p(0.2, 0.9)} C ${p(-0.03, 0.9)} ${p(-0.03, 0.5)} ${p(0.15, 0.5)} C ${p(0.12, 0.1)} ${p(0.43, -0.02)} ${p(0.5, 0.22)} C ${p(0.62, -0.04)} ${p(0.92, 0.08)} ${p(0.86, 0.47)} C ${p(1.05, 0.5)} ${p(1.04, 0.9)} ${p(0.82, 0.9)} Z`
      return (
        <g>
          <path d={d} {...stroke} strokeDasharray={dash || '7 4'} fill={tint(c, '12')} />
          <Title node={node} x={x + 22} y={y + h * 0.5} width={w - 44} anchor="middle" />
        </g>
      )
    }
    case 'node': {
      const depth = 10
      return (
        <g>
          <polygon points={`${x},${y + depth} ${x + depth},${y} ${x + w},${y} ${x + w - depth},${y + depth}`} fill={tint(c, '30')} stroke={c} strokeWidth="1.6" />
          <polygon points={`${x + w - depth},${y + depth} ${x + w},${y} ${x + w},${y + h - depth} ${x + w - depth},${y + h}`} fill={tint(c, '24')} stroke={c} strokeWidth="1.6" />
          <rect x={x} y={y + depth} width={w - depth} height={h - depth} {...stroke} fill={tint(c, '08')} />
          <text x={x + 12} y={y + depth + 22} fontSize="14">{KIND_BADGE[node.variant] || KIND_BADGE.OTHER}</text>
          <Title node={node} x={x + 34} y={y + depth + 20} width={w - depth - 46} />
          <line x1={x + 12} y1={y + depth + 38} x2={x + w - depth - 12} y2={y + depth + 38} stroke={tint(c, '40')} />
          <Rows rows={rows} x={x + 14} y={y + depth + 44} width={w - depth - 28} />
        </g>
      )
    }
    case 'endpoint': {
      const method = String(node.title).split(' ')[0]
      const route = String(node.title).slice(method.length + 1)
      const badge = Math.max(40, method.length * 7 + 14)
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} rx="8" fill="#ffffff" stroke={c} strokeWidth="1.8" />
          <rect x={x} y={y} width={badge} height={h} rx="8" fill={c} />
          <rect x={x + badge - 8} y={y} width="8" height={h} fill={c} />
          <text x={x + badge / 2} y={y + (node.subtitle ? 19 : h / 2 + 4)} fontSize="10.5" fontWeight="700" textAnchor="middle" fill="#ffffff">{method}</text>
          <text x={x + badge + 8} y={y + (node.subtitle ? 19 : h / 2 + 4)} fontSize="11" fontFamily={MONO} fill="#1a1a1a">{clip(route, fits(w - badge - (node.tag ? 34 : 18), 11, true))}</text>
          {node.subtitle && <text x={x + badge + 8} y={y + 36} fontSize="10" fill="#666666">{clip(node.subtitle, fits(w - badge - 16, 10))}</text>}
          {node.tag && <text x={x + w - 10} y={y + 19} fontSize="11" textAnchor="end">{node.tag}</text>}
        </g>
      )
    }
    case 'table': {
      return (
        <g>
          <rect x={x} y={y} width={w} height={h} rx="8" fill="#ffffff" stroke={c} strokeWidth="1.8" />
          <path d={`M ${x} ${y + 30} L ${x} ${y + 8} Q ${x} ${y} ${x + 8} ${y} L ${x + w - 8} ${y} Q ${x + w} ${y} ${x + w} ${y + 8} L ${x + w} ${y + 30} Z`} fill={c} />
          <text x={x + 12} y={y + 20} fontSize="12.5" fontWeight="700" fill="#ffffff" fontFamily={MONO}>{clip(node.title, fits(w - 24, 12.5))}</text>
          <Rows rows={rows} x={x + 12} y={y + 38} width={w - 24} />
        </g>
      )
    }
    default: {
      // class / module / interface / model / generic box
      const classLike = ['class', 'module', 'interface', 'model'].includes(node.shape)
      if (!classLike) {
        return (
          <g>
            <rect x={x} y={y} width={w} height={h} rx="10" {...stroke} />
            <rect x={x} y={y} width="7" height={h} rx="3" fill={c} />
            <Title node={node} x={x + 18} y={y + 27} width={w - 30} />
            <Rows rows={rows} x={x + 18} y={y + 52} width={w - 30} />
          </g>
        )
      }
      const head = 42
      return (
        <g opacity={node.ghost ? 0.55 : 1}>
          <rect x={x} y={y} width={w} height={h} rx="8" {...stroke} strokeWidth="1.8" strokeDasharray={node.shape === 'interface' ? '5 3' : dash} />
          <path d={`M ${x} ${y + head} L ${x} ${y + 8} Q ${x} ${y} ${x + 8} ${y} L ${x + w - 8} ${y} Q ${x + w} ${y} ${x + w} ${y + 8} L ${x + w} ${y + head} Z`} fill={tint(c, '1c')} />
          <text x={x + w / 2} y={y + 16} fontSize="9.5" textAnchor="middle" fill="#666666">{clip(node.subtitle, fits(w - 16, 9.5))}</text>
          <text x={x + w / 2} y={y + 33} fontSize="12.5" fontWeight="700" textAnchor="middle" fill="#1a1a1a">{clip(node.title, fits(w - 16, 12.5))}</text>
          {rows.length > 0 && <line x1={x} y1={y + head} x2={x + w} y2={y + head} stroke={c} strokeOpacity="0.5" />}
          <Rows rows={rows} x={x + 10} y={y + head + 6} width={w - 20} />
        </g>
      )
    }
  }
}

function Markers() {
  const arrow = (id, color) => (
    <marker key={id} id={id} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill={color} />
    </marker>
  )
  return (
    <defs>
      {arrow('mk-call', EDGE_STYLE.call.color)}
      {arrow('mk-flow', EDGE_STYLE.flow.color)}
      {arrow('mk-dep', EDGE_STYLE.dep.color)}
      <marker id="mk-hollow" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="13" markerHeight="13" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
        <path d="M 1 1 L 11 6 L 1 11 z" fill="#ffffff" stroke={EDGE_STYLE.impl.color} strokeWidth="1.4" />
      </marker>
      <marker id="mk-one" viewBox="0 0 14 14" refX="13" refY="7" markerWidth="14" markerHeight="14" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
        <path d="M 6 1 L 6 13 M 10 1 L 10 13" stroke={EDGE_STYLE.fk.color} strokeWidth="1.6" fill="none" />
      </marker>
      <marker id="mk-many" viewBox="0 0 14 14" refX="13" refY="7" markerWidth="14" markerHeight="14" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
        <path d="M 1 7 L 13 1 M 1 7 L 13 13 M 1 7 L 13 7" stroke={EDGE_STYLE.fk.color} strokeWidth="1.6" fill="none" />
      </marker>
    </defs>
  )
}

const markerFor = (edge, end) => {
  if (edge.kind === 'fk') {
    const mark = end === 'start' ? edge.sourceEnd : edge.targetEnd
    return mark === 'one' ? 'url(#mk-one)' : mark === 'many' ? 'url(#mk-many)' : undefined
  }
  if (end === 'start') return undefined
  if (edge.kind === 'impl') return 'url(#mk-hollow)'
  return `url(#mk-${edge.kind === 'flow' ? 'flow' : edge.kind === 'dep' ? 'dep' : 'call'})`
}

// Spacing between ranks leaves room for the widest arrow label (left-to-right layouts put labels
// between the boxes), so labels do not sit on top of them.
function layoutFor(model) {
  const widest = Math.max(0, ...model.edges.map((edge) => (edge.label ? edge.label.length * 5.7 + 24 : 0)))
  const horizontal = model.direction === 'LR'
  const rankGap = horizontal ? Math.min(280, Math.max(72, widest + 48)) : widest ? 58 : 50
  const layout = layoutCompound({ nodes: model.nodes, edges: model.edges, groups: model.groups }, { direction: model.direction, rankGap, nodeGap: 34, innerRankGap: 44, innerNodeGap: 26 })
  return { layout, routes: routeEdges(model.edges, layout.positions, model.direction, layout.paths) }
}

function Graph({ model, layout, routes, selected, highlightIds, onSelect }) {
  const canvas = useCanvas()
  const [hover, setHover] = useState(null)

  const nodeKey = (node) => (node.ref ? `${node.ref.type}:${node.ref.id}` : null)
  const selectedKey = selected ? `${selected.type}:${selected.id}` : null
  const selectedNode = model.nodes.find((node) => nodeKey(node) === selectedKey)
  const groupOfNode = Object.fromEntries(model.nodes.filter((n) => n.group).map((n) => [n.id, n.group]))

  const activeId = hover || selectedNode?.id || null
  const activeIds = new Set()
  if (activeId) {
    activeIds.add(activeId)
    model.nodes.filter((n) => n.group === activeId).forEach((n) => activeIds.add(n.id))
  }
  const touches = (edge) => activeIds.has(edge.source) || activeIds.has(edge.target)
  const neighbours = new Set(activeIds)
  if (activeId) model.edges.filter(touches).forEach((edge) => { neighbours.add(edge.source); neighbours.add(edge.target) })
  const dimTo = hover ? 0.14 : 0.4

  const select = (ref) => {
    if (ref && !canvas.wasDragged()) onSelect?.(ref)
  }

  return (
    <g transform={`translate(${MARGIN} ${MARGIN})`}>
      <Markers />
      {Object.entries(layout.groups).map(([id, group]) => {
        const c = toneColor(group.tone)
        const lit = activeId === id || selectedKey === (group.ref ? `${group.ref.type}:${group.ref.id}` : null)
        return (
          <g key={id} data-group={id} onMouseEnter={() => setHover(id)} onMouseLeave={() => setHover(null)} opacity={activeId && !activeIds.has(id) && !neighbours.has(id) && !model.nodes.some((n) => n.group === id && neighbours.has(n.id)) ? 0.5 : 1}>
            <rect x={group.x} y={group.y} width={group.w} height={group.h} rx="16" fill={tint(c, '08')} stroke={lit ? '#5B2DD8' : c} strokeWidth={lit ? 2.6 : 1.6} strokeDasharray="8 5" />
            <g onClick={() => select(group.ref)} style={{ cursor: group.ref ? 'pointer' : 'default' }}>
              <text x={group.x + 16} y={group.y + 20} fontSize="12.5" fontWeight="700" fill="#1a1a1a">{clip(group.label, fits(group.w - 32, 12.5))}</text>
              {group.sublabel && <text x={group.x + 16} y={group.y + 33} fontSize="10" fill="#666666">{clip(group.sublabel, fits(group.w - 32, 10))}</text>}
            </g>
          </g>
        )
      })}

      {routes.map(({ edge, d }) => {
        const style = EDGE_STYLE[edge.kind] || EDGE_STYLE.call
        const live = !activeId || touches(edge)
        return (
          <g key={`edge-${edge.id}`} data-edge={edge.id} data-kind={edge.kind} opacity={live ? 1 : dimTo} pointerEvents="none">
            <path
              d={d}
              fill="none"
              stroke={style.color}
              strokeWidth={live && activeId ? style.width + 0.7 : style.width}
              strokeDasharray={style.dash}
              markerEnd={markerFor(edge, 'end')}
              markerStart={markerFor(edge, 'start')}
            />
          </g>
        )
      })}

      {model.nodes.map((node) => {
        const box = layout.positions[node.id]
        if (!box) return null
        const key = nodeKey(node)
        const isSelected = key && key === selectedKey
        const isMarked = key && highlightIds?.has(key)
        const faded = activeId && !neighbours.has(node.id) && !(groupOfNode[node.id] && activeIds.has(groupOfNode[node.id]))
        return (
          <g
            key={node.id}
            data-node={node.id}
            data-selected={isSelected ? 'true' : undefined}
            data-marked={isMarked ? 'true' : undefined}
            opacity={faded ? dimTo + 0.2 : 1}
            style={{ cursor: node.ref ? 'pointer' : 'default' }}
            onClick={() => select(node.ref)}
            onMouseEnter={() => setHover(node.id)}
            onMouseLeave={() => setHover(null)}
          >
            <title>{node.tooltip || node.title}</title>
            {(isSelected || isMarked) && (
              <rect x={box.x - 5} y={box.y - 5} width={box.w + 10} height={box.h + 10} rx="14" fill="none" stroke={isSelected ? '#5B2DD8' : '#f59e0b'} strokeWidth={isSelected ? 2.8 : 2.2} strokeDasharray={isSelected ? undefined : '5 3'} />
            )}
            <Shape node={node} box={box} />
          </g>
        )
      })}

      {routes.filter(({ edge }) => edge.label).map(({ edge, lx, ly }) => {
        const live = !activeId || touches(edge)
        const width = edge.label.length * 5.7 + 14
        const flow = edge.kind === 'flow'
        return (
          <g key={`label-${edge.id}`} opacity={live ? 1 : dimTo} pointerEvents="none">
            <title>{edge.tooltip || edge.label}</title>
            <rect x={lx - width / 2} y={ly - 9} width={width} height="18" rx="9" fill="#ffffff" stroke={flow ? EDGE_STYLE.flow.color : edge.kind === 'fk' ? '#a7f3d0' : '#e5e0ff'} />
            <text x={lx} y={ly + 4} fontSize="10.5" fontWeight={flow ? 600 : 500} textAnchor="middle" fill="#444444">{edge.label}</text>
          </g>
        )
      })}
    </g>
  )
}

function GraphDiagram({ model, selected, highlightIds, onSelect, label, resetKey }) {
  const { layout, routes } = useMemo(() => layoutFor(model), [model])
  // Long arrows can bulge past the boxes; make the drawing area cover every curve.
  const bounds = useMemo(() => {
    let width = layout.width
    let height = layout.height
    Object.values(layout.paths || {}).forEach((lane) => lane.forEach((pt) => { width = Math.max(width, pt.x + 20); height = Math.max(height, pt.y + 20) }))
    return { width: width + MARGIN * 2, height: height + MARGIN * 2 }
  }, [layout])
  return (
    <DiagramCanvas width={bounds.width} height={bounds.height} label={label} resetKey={resetKey}>
      <Graph model={model} layout={layout} routes={routes} selected={selected} highlightIds={highlightIds} onSelect={onSelect} />
    </DiagramCanvas>
  )
}

export default GraphDiagram
