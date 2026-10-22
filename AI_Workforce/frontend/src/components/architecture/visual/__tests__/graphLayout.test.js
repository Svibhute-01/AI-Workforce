import test from 'node:test'
import assert from 'node:assert/strict'
import { layoutCompound, layoutLayered, routeEdges } from '../graphLayout.js'

const node = (id, extra = {}) => ({ id, w: 100, h: 40, ...extra })
const overlaps = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h

test('a chain C1 -> C2 -> C3 is laid out as three ranks in order', () => {
  const { positions } = layoutLayered([node('C1'), node('C2'), node('C3')], [
    { source: 'C1', target: 'C2' }, { source: 'C2', target: 'C3' },
  ])
  assert.deepEqual([positions.C1.rank, positions.C2.rank, positions.C3.rank], [0, 1, 2])
  assert.ok(positions.C1.y < positions.C2.y && positions.C2.y < positions.C3.y)
})

test('left-to-right layout flows along the x axis and keeps the node sizes', () => {
  const { positions } = layoutLayered([node('A', { w: 120, h: 50 }), node('B', { w: 80, h: 30 })], [{ source: 'A', target: 'B' }], { direction: 'LR' })
  assert.ok(positions.A.x < positions.B.x)
  assert.deepEqual([positions.A.w, positions.A.h, positions.B.w, positions.B.h], [120, 50, 80, 30])
})

test('no two nodes overlap, including wide ranks with shared targets', () => {
  const ids = ['A', 'B', 'C', 'D', 'E', 'F']
  const nodes = ids.map((id) => node(id, { w: 90 + (id.charCodeAt(0) % 3) * 30 }))
  const edges = [['A', 'D'], ['B', 'D'], ['C', 'D'], ['A', 'E'], ['C', 'F'], ['D', 'F']].map(([source, target]) => ({ source, target }))
  const { positions } = layoutLayered(nodes, edges)
  const boxes = Object.values(positions)
  for (let i = 0; i < boxes.length; i += 1) for (let j = i + 1; j < boxes.length; j += 1) assert.equal(overlaps(boxes[i], boxes[j]), false)
})

test('cycles do not break the layout and every node still gets a position', () => {
  const { positions } = layoutLayered([node('A'), node('B'), node('C')], [
    { source: 'A', target: 'B' }, { source: 'B', target: 'C' }, { source: 'C', target: 'A' },
  ])
  assert.deepEqual(Object.keys(positions).sort(), ['A', 'B', 'C'])
  assert.equal(new Set(Object.values(positions).map((p) => p.rank)).size, 3)
})

test('pinned nodes go to the first and last rank (actors on top, external systems at the bottom)', () => {
  const nodes = [node('actor', { pin: 'first' }), node('api'), node('db'), node('mail', { pin: 'last' })]
  const edges = [['actor', 'api'], ['api', 'db'], ['api', 'mail']].map(([source, target]) => ({ source, target }))
  const { positions } = layoutLayered(nodes, edges)
  assert.equal(positions.actor.rank, 0)
  assert.ok(positions.api.rank > 0 && positions.db.rank > 0)
  assert.ok(positions.mail.rank > Math.max(positions.api.rank, positions.db.rank))
})

test('edges to unknown nodes, self loops and duplicates are ignored', () => {
  const { positions } = layoutLayered([node('A'), node('B')], [
    { source: 'A', target: 'A' }, { source: 'A', target: 'X' }, { source: 'A', target: 'B' }, { source: 'A', target: 'B' },
  ])
  assert.equal(positions.B.rank, 1)
})

test('an empty graph lays out to nothing', () => {
  assert.deepEqual(layoutLayered([], []), { positions: {}, width: 0, height: 0, paths: {} })
})

test('group members stay inside their group box and groups do not overlap each other', () => {
  const nodes = [node('M1', { group: 'C2' }), node('M2', { group: 'C2' }), node('M3', { group: 'C3' }), node('A', { pin: 'first' })]
  const edges = [['M1', 'M2'], ['A', 'M1'], ['M2', 'M3']].map(([source, target]) => ({ source, target }))
  const result = layoutCompound({ nodes, edges, groups: [{ id: 'C2', label: 'API' }, { id: 'C3', label: 'Data' }] })
  for (const [id, group] of [['M1', 'C2'], ['M2', 'C2'], ['M3', 'C3']]) {
    const box = result.groups[group]
    const p = result.positions[id]
    assert.ok(p.x >= box.x && p.y >= box.y + box.title && p.x + p.w <= box.x + box.w && p.y + p.h <= box.y + box.h, `${id} inside ${group}`)
  }
  assert.equal(overlaps(result.groups.C2, result.groups.C3), false)
  assert.ok(result.positions.A.y + result.positions.A.h <= result.groups.C2.y, 'the pinned actor sits above the boundary')
})

test('edges route between node borders and parallel edges are spread along the side', () => {
  const positions = { A: { x: 0, y: 0, w: 100, h: 40 }, B: { x: -80, y: 140, w: 100, h: 40 }, C: { x: 80, y: 140, w: 100, h: 40 } }
  const routes = routeEdges([{ id: 'e1', source: 'A', target: 'B' }, { id: 'e2', source: 'A', target: 'C' }], positions)
  assert.equal(routes.length, 2)
  assert.ok(routes.every((route) => route.from[1] === 40 && route.to[1] === 140), 'bottom of A to top of B / C')
  assert.notEqual(routes[0].from[0], routes[1].from[0])
  assert.ok(routes.every((route) => route.d.startsWith('M ') && Number.isFinite(route.lx) && Number.isFinite(route.ly)))
})

test('edges between same-level boxes leave from the sides', () => {
  const positions = { A: { x: 0, y: 0, w: 100, h: 40 }, B: { x: 200, y: 0, w: 100, h: 40 } }
  const [route] = routeEdges([{ id: 'e', source: 'A', target: 'B' }], positions)
  assert.deepEqual([route.from[0], route.to[0]], [100, 200])
})

test('an edge that spans several ranks is routed around the boxes in between, not through them', () => {
  const nodes = [node('A'), node('B'), node('C'), node('D')]
  const edges = [['A', 'B'], ['B', 'C'], ['C', 'D'], ['A', 'D']].map(([source, target]) => ({ source, target }))
  const withIds = edges.map((e, i) => ({ ...e, id: `e${i}` }))
  const result = layoutCompound({ nodes, edges: withIds, groups: [] })
  assert.equal(result.paths.e3.length, 2, 'one lane point per rank crossed')
  const routes = routeEdges(withIds, result.positions, 'TB', result.paths)
  const long = routes.find((r) => r.id === 'e3')
  const lanePoints = result.paths.e3
  for (const point of lanePoints) {
    for (const id of ['B', 'C']) {
      const box = result.positions[id]
      const inside = point.x > box.x && point.x < box.x + box.w && point.y > box.y && point.y < box.y + box.h
      assert.equal(inside, false, `lane point inside ${id}`)
    }
  }
  assert.ok(long.d.split(' C ').length === 4, 'one curve segment per lane point plus the ends')
  assert.ok(Number.isFinite(long.lx) && Number.isFinite(long.ly))
})

test('lane points also work in left-to-right layouts and for edges that point backwards', () => {
  const nodes = [node('A'), node('B'), node('C')]
  const edges = [['A', 'B'], ['B', 'C'], ['C', 'A']].map(([source, target], i) => ({ source, target, id: `e${i}` }))
  const result = layoutCompound({ nodes, edges, groups: [] }, { direction: 'LR' })
  const routes = routeEdges(edges, result.positions, 'LR', result.paths)
  assert.equal(routes.length, 3)
  assert.ok(routes.every((r) => r.d.startsWith('M ') && !r.d.includes('NaN')))
})
