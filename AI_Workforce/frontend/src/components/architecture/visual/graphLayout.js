// Layered graph layout and edge routing for the architecture diagrams.
//
// Pure functions (no DOM, no React) so they can be tested with `node --test`. The graphs here are
// small (a handful to a few dozen nodes), so a compact layered layout is enough:
//   1. rank nodes with a longest-path pass (cycles are broken by reversing back edges),
//   2. order each rank with barycentre sweeps to reduce crossings,
//   3. place nodes, pulling each toward the centre of its neighbours while keeping a minimum gap.
// `pin: 'first' | 'last'` forces a node into the first / last rank (actors on top, external
// systems at the bottom). Groups (system boundary, component boundary) are laid out first and
// then placed as one block in the outer layout.

const DEFAULTS = { direction: 'TB', rankGap: 64, nodeGap: 32 }

function uniqueLinks(nodes, edges) {
  const known = new Set(nodes.map((node) => node.id))
  const seen = new Set()
  const links = []
  edges.forEach((edge) => {
    if (!known.has(edge.source) || !known.has(edge.target) || edge.source === edge.target) return
    const key = `${edge.source}>${edge.target}`
    if (seen.has(key)) return
    seen.add(key)
    links.push({ source: edge.source, target: edge.target })
  })
  return links
}

function assignRanks(items, links) {
  const index = new Map(items.map((item, i) => [item.id, i]))
  const free = items.map((_, i) => i).filter((i) => !items[i].pin)
  const isFree = new Set(free)
  const out = items.map(() => [])
  links.forEach(({ source, target }) => {
    const s = index.get(source)
    const t = index.get(target)
    if (isFree.has(s) && isFree.has(t)) out[s].push(t)
  })

  // Break cycles: an edge back to a node still on the DFS stack is reversed for ranking only.
  const state = items.map(() => 0)
  const dag = []
  const visit = (u) => {
    state[u] = 1
    out[u].forEach((v) => {
      if (state[v] === 1) dag.push([v, u])
      else {
        dag.push([u, v])
        if (state[v] === 0) visit(v)
      }
    })
    state[u] = 2
  }
  free.forEach((i) => { if (state[i] === 0) visit(i) })

  const rank = items.map(() => 0)
  const indegree = items.map(() => 0)
  const next = items.map(() => [])
  dag.forEach(([u, v]) => { next[u].push(v); indegree[v] += 1 })
  const queue = free.filter((i) => indegree[i] === 0)
  while (queue.length) {
    const u = queue.shift()
    next[u].forEach((v) => {
      rank[v] = Math.max(rank[v], rank[u] + 1)
      indegree[v] -= 1
      if (indegree[v] === 0) queue.push(v)
    })
  }

  const firsts = items.map((_, i) => i).filter((i) => items[i].pin === 'first')
  const lasts = items.map((_, i) => i).filter((i) => items[i].pin === 'last')
  const base = firsts.length ? 1 : 0
  free.forEach((i) => { rank[i] += base })
  firsts.forEach((i) => { rank[i] = 0 })
  const deepest = free.length ? Math.max(...free.map((i) => rank[i])) : base - 1
  lasts.forEach((i) => { rank[i] = Math.max(deepest + 1, 0) })
  return rank
}

function orderRanks(items, links, rank) {
  const index = new Map(items.map((item, i) => [item.id, i]))
  const rankCount = Math.max(...rank, 0) + 1
  const layers = Array.from({ length: rankCount }, () => [])
  items.forEach((_, i) => layers[rank[i]].push(i))
  const neighbours = items.map(() => [])
  links.forEach(({ source, target }) => {
    const s = index.get(source)
    const t = index.get(target)
    neighbours[s].push(t)
    neighbours[t].push(s)
  })

  const position = items.map(() => 0)
  const refresh = () => layers.forEach((layer) => layer.forEach((node, i) => { position[node] = layer.length > 1 ? i / (layer.length - 1) : 0.5 }))
  refresh()

  const sweep = (from, to, step) => {
    for (let r = from; r !== to; r += step) {
      const layer = layers[r]
      const keyed = layer.map((node, i) => {
        const others = neighbours[node].filter((other) => (step > 0 ? rank[other] < r : rank[other] > r))
        const key = others.length ? others.reduce((sum, other) => sum + position[other], 0) / others.length : position[node]
        return { node, key, i }
      })
      keyed.sort((a, b) => a.key - b.key || a.i - b.i)
      layers[r] = keyed.map((entry) => entry.node)
      layers[r].forEach((node, i) => { position[node] = layers[r].length > 1 ? i / (layers[r].length - 1) : 0.5 })
    }
  }
  for (let pass = 0; pass < 4; pass += 1) {
    sweep(1, rankCount, 1)
    sweep(rankCount - 2, -1, -1)
  }
  return { layers, neighbours }
}

export function layoutLayered(nodes, edges, options = {}) {
  const { direction, rankGap, nodeGap } = { ...DEFAULTS, ...options }
  if (!nodes.length) return { positions: {}, width: 0, height: 0, paths: {} }
  const horizontal = direction === 'LR'
  // Everything is computed as a top-to-bottom layout; left-to-right swaps the axes at the end.
  const items = nodes.map((node) => ({ ...node, w: horizontal ? node.h : node.w, h: horizontal ? node.w : node.h }))
  const realCount = items.length
  const realLinks = uniqueLinks(items, edges)
  const rank0 = assignRanks(items, realLinks)

  // An edge that spans several ranks gets one invisible placeholder per rank it crosses, so the
  // ordering and placement leave a lane for it instead of drawing it through a box.
  const rank = [...rank0]
  const rankOf = new Map(items.map((item, i) => [item.id, rank0[i]]))
  const links = []
  const chains = []
  realLinks.forEach(({ source, target }) => {
    const reversed = rankOf.get(source) > rankOf.get(target)
    const [from, to] = reversed ? [target, source] : [source, target]
    const span = rankOf.get(to) - rankOf.get(from)
    if (span <= 1) { links.push({ source: from, target: to }); return }
    let previous = from
    const ids = []
    for (let r = rankOf.get(from) + 1; r < rankOf.get(to); r += 1) {
      const id = `~${source}>${target}~${r}`
      items.push({ id, w: 8, h: 0, dummy: true })
      rank.push(r)
      ids.push(id)
      links.push({ source: previous, target: id })
      previous = id
    }
    links.push({ source: previous, target: to })
    chains.push({ key: `${source}>${target}`, ids: reversed ? ids.reverse() : ids })
  })
  const { layers, neighbours } = orderRanks(items, links, rank)

  const x = items.map(() => 0)
  const y = items.map(() => 0)
  let cursor = 0
  layers.forEach((layer) => {
    const tallest = Math.max(0, ...layer.map((i) => items[i].h))
    layer.forEach((i) => { y[i] = cursor + (tallest - items[i].h) / 2 })
    cursor += tallest + rankGap
  })

  const center = (i) => x[i] + items[i].w / 2
  layers.forEach((layer) => {
    const total = layer.reduce((sum, i) => sum + items[i].w, 0) + nodeGap * Math.max(layer.length - 1, 0)
    let at = -total / 2
    layer.forEach((i) => { x[i] = at; at += items[i].w + nodeGap })
  })

  const settle = (layer, wanted) => {
    const forward = []
    let edge = -Infinity
    layer.forEach((i) => {
      const left = Math.max(edge + nodeGap, wanted(i) - items[i].w / 2)
      forward.push(left)
      edge = left + items[i].w
    })
    const backward = new Array(layer.length)
    edge = Infinity
    for (let k = layer.length - 1; k >= 0; k -= 1) {
      const i = layer[k]
      const left = Math.min(edge - nodeGap - items[i].w, wanted(i) - items[i].w / 2)
      backward[k] = left
      edge = left
    }
    // Both placements keep the minimum gap, so their average does too.
    layer.forEach((i, k) => { x[i] = (forward[k] + backward[k]) / 2 })
  }
  for (let pass = 0; pass < 6; pass += 1) {
    const order = pass % 2 === 0 ? layers.map((_, r) => r) : layers.map((_, r) => layers.length - 1 - r)
    order.forEach((r) => {
      const towards = pass % 2 === 0 ? (other) => rank[other] < r : (other) => rank[other] > r
      settle(layers[r], (i) => {
        const near = neighbours[i].filter(towards).concat(neighbours[i].filter((o) => !towards(o) && rank[o] !== r))
        const usable = near.length ? near : [i]
        return usable.reduce((sum, other) => sum + center(other), 0) / usable.length
      })
    })
  }

  const minX = Math.min(...items.map((_, i) => x[i]))
  const positions = {}
  let width = 0
  let height = 0
  items.forEach((item, i) => {
    if (i >= realCount) return
    const tx = x[i] - minX
    const ty = y[i]
    const box = horizontal
      ? { x: ty, y: tx, w: item.h, h: item.w }
      : { x: tx, y: ty, w: item.w, h: item.h }
    positions[item.id] = { ...box, rank: rank[i] }
    width = Math.max(width, box.x + box.w)
    height = Math.max(height, box.y + box.h)
  })

  // Lane points of the long edges, in the direction of the edge (source -> target).
  const slot = new Map(items.map((item, i) => [item.id, i]))
  const paths = {}
  chains.forEach(({ key, ids }) => {
    paths[key] = ids.map((id) => {
      const i = slot.get(id)
      const cx = x[i] - minX + items[i].w / 2
      const cy = y[i] + items[i].h / 2
      return horizontal ? { x: cy, y: cx } : { x: cx, y: cy }
    })
  })
  return { positions, width, height, paths }
}

/**
 * Lay out nodes that may belong to a group (a boundary box). Each group is laid out on its own,
 * then treated as one node of the outer layout. Edges that touch a group member count as edges
 * of the group for the outer ranking.
 */
export function layoutCompound({ nodes, edges, groups = [] }, options = {}) {
  const direction = options.direction || 'TB'
  const pad = options.groupPad ?? 22
  const title = options.groupTitle ?? 32
  const groupIds = new Map(groups.map((group) => [group.id, group]))
  const members = new Map(groups.map((group) => [group.id, []]))
  const groupOf = new Map()
  nodes.forEach((node) => {
    if (node.group && groupIds.has(node.group)) {
      members.get(node.group).push(node)
      groupOf.set(node.id, node.group)
    }
  })

  const inner = {}
  groups.forEach((group) => {
    const own = members.get(group.id)
    if (!own.length) return
    const ids = new Set(own.map((node) => node.id))
    const layout = layoutLayered(own, edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)), {
      direction: group.direction || options.innerDirection || direction,
      rankGap: options.innerRankGap ?? 46,
      nodeGap: options.innerNodeGap ?? 24,
    })
    inner[group.id] = { layout, w: layout.width + pad * 2, h: layout.height + pad * 2 + title }
  })

  const outerNodes = nodes.filter((node) => !groupOf.has(node.id))
  groups.forEach((group) => {
    if (inner[group.id]) outerNodes.push({ id: group.id, w: inner[group.id].w, h: inner[group.id].h, pin: group.pin })
  })
  const outerId = (id) => groupOf.get(id) || id
  const outerEdges = edges.map((edge) => ({ source: outerId(edge.source), target: outerId(edge.target) }))
  const outer = layoutLayered(outerNodes, outerEdges, {
    direction,
    rankGap: options.rankGap ?? DEFAULTS.rankGap,
    nodeGap: options.nodeGap ?? DEFAULTS.nodeGap,
  })

  const positions = {}
  const boxes = {}
  nodes.forEach((node) => {
    if (!groupOf.has(node.id)) positions[node.id] = outer.positions[node.id]
  })
  groups.forEach((group) => {
    if (!inner[group.id]) return
    const box = outer.positions[group.id]
    boxes[group.id] = { ...box, label: group.label, sublabel: group.sublabel, tone: group.tone, title, ref: group.ref }
    members.get(group.id).forEach((node) => {
      const local = inner[group.id].layout.positions[node.id]
      positions[node.id] = { ...local, x: box.x + pad + local.x, y: box.y + title + pad + local.y }
    })
  })

  const paths = {}
  edges.forEach((edge) => {
    const sg = groupOf.get(edge.source)
    const tg = groupOf.get(edge.target)
    if (sg && sg === tg && inner[sg]) {
      const lane = inner[sg].layout.paths[`${edge.source}>${edge.target}`]
      const origin = boxes[sg]
      if (lane?.length) paths[edge.id] = lane.map((pt) => ({ x: origin.x + pad + pt.x, y: origin.y + title + pad + pt.y }))
    } else {
      const lane = outer.paths[`${outerId(edge.source)}>${outerId(edge.target)}`]
      if (lane?.length) paths[edge.id] = lane
    }
  })
  return { positions, groups: boxes, width: outer.width, height: outer.height, paths }
}

const EXIT = { top: [0, -1], bottom: [0, 1], left: [-1, 0], right: [1, 0] }

function chooseSides(a, b, direction) {
  const below = b.y >= a.y + a.h - 1
  const above = b.y + b.h <= a.y + 1
  const rightOf = b.x >= a.x + a.w - 1
  const leftOf = b.x + b.w <= a.x + 1
  if (direction === 'LR') {
    if (rightOf) return ['right', 'left']
    if (leftOf) return ['left', 'right']
    return b.y + b.h / 2 >= a.y + a.h / 2 ? ['bottom', 'top'] : ['top', 'bottom']
  }
  if (below) return ['bottom', 'top']
  if (above) return ['top', 'bottom']
  return b.x + b.w / 2 >= a.x + a.w / 2 ? ['right', 'left'] : ['left', 'right']
}

/**
 * Curves for every edge between the laid-out boxes. Edges that share a side of a node are spread
 * along that side (ordered by where the other end is) so parallel arrows do not overlap.
 */
export function routeEdges(edges, positions, direction = 'TB', lanes = {}) {
  const routed = []
  const ports = new Map()
  const note = (nodeId, side, edgeId, other) => {
    const key = `${nodeId}|${side}`
    if (!ports.has(key)) ports.set(key, [])
    ports.get(key).push({ edgeId, other })
  }
  edges.forEach((edge) => {
    const a = positions[edge.source]
    const b = positions[edge.target]
    if (!a || !b || edge.source === edge.target) return
    const lane = lanes[edge.id]
    let [sideA, sideB] = chooseSides(a, b, direction)
    if (lane?.length) {
      // Long edge: leave and arrive along the rank axis, steering by the first / last lane point.
      const first = lane[0]
      const last = lane[lane.length - 1]
      if (direction === 'LR') {
        sideA = first.x >= a.x + a.w / 2 ? 'right' : 'left'
        sideB = last.x <= b.x + b.w / 2 ? 'left' : 'right'
      } else {
        sideA = first.y >= a.y + a.h / 2 ? 'bottom' : 'top'
        sideB = last.y <= b.y + b.h / 2 ? 'top' : 'bottom'
      }
    }
    const alongX = (side) => side === 'top' || side === 'bottom'
    const towardsA = lane?.length ? lane[0] : { x: b.x + b.w / 2, y: b.y + b.h / 2 }
    const towardsB = lane?.length ? lane[lane.length - 1] : { x: a.x + a.w / 2, y: a.y + a.h / 2 }
    note(edge.source, sideA, `${edge.id}:s`, alongX(sideA) ? towardsA.x : towardsA.y)
    note(edge.target, sideB, `${edge.id}:t`, alongX(sideB) ? towardsB.x : towardsB.y)
    routed.push({ edge, sideA, sideB, lane })
  })
  const slot = new Map()
  ports.forEach((list) => {
    list.sort((p, q) => p.other - q.other)
    list.forEach((port, i) => slot.set(port.edgeId, { index: i, count: list.length }))
  })
  const attach = (box, side, edgeId) => {
    const { index, count } = slot.get(edgeId)
    const t = (index + 1) / (count + 1)
    if (side === 'top') return [box.x + box.w * t, box.y]
    if (side === 'bottom') return [box.x + box.w * t, box.y + box.h]
    if (side === 'left') return [box.x, box.y + box.h * t]
    return [box.x + box.w, box.y + box.h * t]
  }
  return routed.map(({ edge, sideA, sideB, lane }) => {
    const [sx, sy] = attach(positions[edge.source], sideA, `${edge.id}:s`)
    const [tx, ty] = attach(positions[edge.target], sideB, `${edge.id}:t`)
    if (lane?.length) {
      const points = [{ x: sx, y: sy }, ...lane, { x: tx, y: ty }]
      let d = `M ${sx} ${sy}`
      for (let i = 0; i < points.length - 1; i += 1) {
        const p = points[i]
        const q = points[i + 1]
        d += direction === 'LR'
          ? ` C ${(p.x + q.x) / 2} ${p.y}, ${(p.x + q.x) / 2} ${q.y}, ${q.x} ${q.y}`
          : ` C ${p.x} ${(p.y + q.y) / 2}, ${q.x} ${(p.y + q.y) / 2}, ${q.x} ${q.y}`
      }
      const mid = Math.floor((points.length - 1) / 2)
      return {
        id: edge.id, edge, d, from: [sx, sy], to: [tx, ty],
        lx: (points[mid].x + points[mid + 1].x) / 2, ly: (points[mid].y + points[mid + 1].y) / 2,
      }
    }
    const k = Math.min(120, Math.max(36, Math.hypot(tx - sx, ty - sy) / 2.2))
    const [ax, ay] = EXIT[sideA]
    const [bx, by] = EXIT[sideB]
    const c1 = [sx + ax * k, sy + ay * k]
    const c2 = [tx + bx * k, ty + by * k]
    const at = (p0, p1, p2, p3, t) => (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
    return {
      id: edge.id,
      edge,
      d: `M ${sx} ${sy} C ${c1[0]} ${c1[1]}, ${c2[0]} ${c2[1]}, ${tx} ${ty}`,
      from: [sx, sy],
      to: [tx, ty],
      lx: at(sx, c1[0], c2[0], tx, 0.5),
      ly: at(sy, c1[1], c2[1], ty, 0.5),
    }
  })
}
