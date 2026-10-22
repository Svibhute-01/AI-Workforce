import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  buildApiDiagram, buildClassDiagram, buildComponentDiagram, buildContextDiagram, buildDataFlowDiagram,
  buildDeploymentDiagram, buildDetailedComponentDiagram, buildErDiagram, buildHldSequence, buildIndex,
  buildLldSequence, componentOf, componentsWith, describeRef,
} from '../diagramModels.js'
import { layoutCompound } from '../graphLayout.js'

// A real design produced by the backend Architect agent (RA -> PM -> Architect) for the test project.
const real = JSON.parse(readFileSync(new URL('./fixtures/registration-design.json', import.meta.url), 'utf8'))
const clone = (value) => JSON.parse(JSON.stringify(value))
const hld = real.hld
const lld = real.lld
const ids = (items) => items.map((item) => item.id)
const byId = (model, id) => model.nodes.find((node) => node.id === id)

// ---------------------------------------------------------------- HLD ----

test('system context: the system, its actors and the external systems come from the design', () => {
  const model = buildContextDiagram(hld, 'Customer Registration')
  assert.deepEqual(ids(model.nodes).sort(), ['ACTOR:A1', 'C4', 'SYSTEM'])
  assert.equal(byId(model, 'SYSTEM').title, 'Customer Registration')
  assert.deepEqual(byId(model, 'SYSTEM').rows.map((r) => r.text), ['Web Client', 'Registration API', 'Account Database'])
  assert.equal(byId(model, 'ACTOR:A1').shape, 'actor')
  assert.equal(byId(model, 'C4').shape, 'cloud')
  const actorEdge = model.edges.find((e) => e.source === 'ACTOR:A1')
  assert.deepEqual([actorEdge.target, actorEdge.label], ['SYSTEM', 'Registers through the web form'])
  const mail = model.edges.find((e) => e.target === 'C4')
  assert.deepEqual([mail.source, mail.label], ['SYSTEM', 'HTTPS'])
  assert.deepEqual(model.notes, [])
})

test('system context: an integration that is the same thing as an external component is not drawn twice', () => {
  const model = buildContextDiagram(hld, 'X')
  assert.equal(model.nodes.filter((n) => n.shape === 'cloud').length, 1)
  assert.equal(hld.integrations[0].name, 'Email delivery', 'the integration has a different name than the component')
  assert.equal(model.edges.find((e) => e.target === 'C4').label, 'HTTPS')
})

test('system context: a design without actors says so instead of inventing one', () => {
  const design = clone(hld)
  design.actors = []
  const model = buildContextDiagram(design, 'X')
  assert.equal(model.nodes.some((n) => n.shape === 'actor'), false)
  assert.match(model.notes[0], /names no actors/)
})

test('system context: an integration with no matching external component becomes its own external node', () => {
  const design = clone(hld)
  design.components = design.components.filter((c) => c.component_id !== 'C4')
  design.relationships = design.relationships.filter((r) => r.target_component_id !== 'C4')
  design.data_flows[0].steps = design.data_flows[0].steps.slice(0, 2)
  design.integrations = [{ integration_id: 'INT9', name: 'Payment gateway', purpose: 'Charge cards', component_id: 'C2', protocol: 'REST', grounding: 'EXPLICIT' }]
  const model = buildContextDiagram(design, 'X')
  const node = byId(model, 'INT:INT9')
  assert.deepEqual([node.shape, node.title], ['cloud', 'Payment gateway'])
  assert.equal(model.edges.find((e) => e.target === 'INT:INT9').label, 'REST')
})

test('component architecture: boundary holds the internal components; actors and external systems sit outside', () => {
  const model = buildComponentDiagram(hld, lld, 'Customer Registration')
  assert.deepEqual(model.groups.map((g) => g.id), ['BOUNDARY'])
  assert.deepEqual(model.nodes.filter((n) => n.group === 'BOUNDARY').map((n) => n.id).sort(), ['C1', 'C2', 'C3'])
  assert.equal(byId(model, 'C4').group, undefined)
  assert.equal(byId(model, 'C4').pin, 'last')
  assert.equal(byId(model, 'ACTOR:A1').pin, 'first')
  assert.deepEqual(['C1', 'C2', 'C3', 'C4'].map((id) => byId(model, id).shape), ['frontend', 'box', 'database', 'cloud'])
  assert.deepEqual(model.edges.filter((e) => e.id.startsWith('R')).map((e) => [e.source, e.target, e.label]), [
    ['C1', 'C2', 'HTTPS/JSON'], ['C2', 'C3', 'SQL'], ['C2', 'C4', 'HTTPS'],
  ])
  assert.ok(model.edges.some((e) => e.source === 'ACTOR:A1' && e.target === 'C1'))
  assert.match(byId(model, 'C2').rows[0].text, /3 LLD modules/)
})

test('component architecture is generated from the data: add a component and it appears with its shape and protocol', () => {
  const design = clone(hld)
  design.components.push({ component_id: 'C5', name: 'Agent Runtime', type: 'AI_SERVICE', description: 'Runs agents', responsibilities: ['x'], technology: 'LangGraph', grounding: 'ASSUMED', requirement_ids: [], task_ids: [], rationale: 'r' })
  design.relationships.push({ relationship_id: 'R9', source_component_id: 'C2', target_component_id: 'C5', interaction: 'FUNCTION_CALL', description: 'runs', data_exchanged: null, protocol: 'LLM' })
  const model = buildComponentDiagram(design, lld, 'X')
  assert.deepEqual([byId(model, 'C5').shape, byId(model, 'C5').group, byId(model, 'C5').subtitle], ['ai', 'BOUNDARY', 'AI SERVICE · LangGraph'])
  assert.equal(model.edges.find((e) => e.id === 'R9').label, 'LLM')
})

test('a relationship without a protocol is labelled with its interaction, and OTHER gets no label', () => {
  const design = clone(hld)
  design.relationships[0].protocol = null
  design.relationships[1].protocol = null
  design.relationships[1].interaction = 'OTHER'
  const model = buildComponentDiagram(design, lld, 'X')
  assert.deepEqual(model.edges.filter((e) => e.id.startsWith('R')).map((e) => e.label), ['HTTP', '', 'HTTPS'])
})

test('data flow: numbered steps between the components the flow passes through', () => {
  const model = buildDataFlowDiagram(hld, 'DF1', lld)
  assert.equal(model.direction, 'LR')
  assert.deepEqual(model.nodes.map((n) => n.id), ['C1', 'C2', 'C3', 'C4'])
  assert.deepEqual(model.edges.map((e) => [e.source, e.target, e.seq]), [['C1', 'C2', 1], ['C2', 'C3', 2], ['C2', 'C4', 3]])
  assert.equal(model.edges[0].label, '1. Submit email and password')
  assert.equal(buildDataFlowDiagram(hld, 'unknown', lld).flow.flow_id, 'DF1')
  assert.match(buildDataFlowDiagram({ ...hld, data_flows: [] }, 'DF1', lld).empty, /no data flows/)
})

test('deployment: nodes list the components they host, links come from the component relationships', () => {
  const model = buildDeploymentDiagram(hld, lld)
  assert.deepEqual(model.nodes.map((n) => n.id), ['DN1', 'DN2', 'DN3', 'C4'])
  assert.deepEqual(byId(model, 'DN2').rows.map((r) => r.text), ['Registration API'])
  assert.deepEqual(model.edges.map((e) => [e.source, e.target, e.label]), [['DN1', 'DN2', 'HTTPS/JSON'], ['DN2', 'DN3', 'SQL'], ['DN2', 'C4', 'HTTPS']])
  assert.equal(byId(model, 'DN1').variant, 'CLIENT_DEVICE')
})

test('deployment: a design saved without deployment nodes explains it and offers the written deployment notes', () => {
  const old = clone(hld)
  delete old.deployment
  const model = buildDeploymentDiagram(old, lld)
  assert.match(model.empty, /no structured deployment/)
  assert.deepEqual(model.fallback.map((q) => q.category), ['DEPLOYMENT'])
})

test('deployment: components that are not placed anywhere are reported', () => {
  const design = clone(hld)
  design.deployment = design.deployment.slice(0, 2)
  assert.match(buildDeploymentDiagram(design, lld).notes[0], /Account Database/)
})

test('HLD sequence: lifelines in order of appearance, starting with the actor who triggers the flow', () => {
  const model = buildHldSequence(hld, 'DF1', lld)
  assert.deepEqual(model.participants.map((p) => p.id), ['ACTOR:A1', 'C1', 'C2', 'C3', 'C4'])
  assert.deepEqual(model.messages.map((m) => [m.from, m.to]), [['ACTOR:A1', 'C1'], ['C1', 'C2'], ['C2', 'C3'], ['C2', 'C4']])
  assert.deepEqual(model.messages.map((m) => m.order), [0, 1, 2, 3])
})

// ---------------------------------------------------------------- LLD ----

test('class diagram: the modules of one component, with their dependencies inside the component boundary', () => {
  const model = buildClassDiagram(hld, lld, 'C2')
  assert.deepEqual(model.nodes.filter((n) => n.shape === 'class').map((n) => n.id), ['M1', 'M2', 'M3'])
  assert.ok(model.nodes.every((n) => n.group === 'C2'))
  assert.deepEqual(model.edges.filter((e) => e.kind === 'dep').map((e) => [e.source, e.target]), [['M1', 'M2'], ['M2', 'M3']])
  const iface = model.nodes.filter((n) => n.shape === 'interface')
  assert.deepEqual(iface.map((n) => n.id), lld.interfaces.map((i) => i.interface_id), 'the design\'s own interfaces are drawn')
  assert.ok(model.edges.some((e) => e.kind === 'impl' && e.target === iface[0].id))
  assert.deepEqual(model.groups.map((g) => g.id), ['C2'])
  assert.match(byId(model, 'M1').subtitle, /controller/)
  assert.ok(byId(model, 'M1').rows.length > 0, 'methods are listed')
  assert.match(buildClassDiagram(hld, lld, 'C1').empty, /no LLD modules/)
})

test('class diagram: modules of other components that depend on this one appear as faded ghosts', () => {
  const design = clone(lld)
  design.modules.push({ ...clone(design.modules[0]), module_id: 'M9', component_id: 'C1', name: 'RegistrationForm', kind: 'UI_COMPONENT', depends_on_module_ids: ['M1'] })
  const model = buildClassDiagram(hld, design, 'C2')
  const ghost = byId(model, 'M9')
  assert.deepEqual([ghost.ghost, ghost.group], [true, undefined])
  assert.match(ghost.subtitle, /in Web Client/)
  assert.ok(model.edges.some((e) => e.source === 'M9' && e.target === 'M1'))
  assert.ok(model.notes.length === 1)
})

test('class diagram: interfaces and business rules attached to modules are drawn', () => {
  const design = clone(lld)
  design.interfaces = [{ interface_id: 'IF1', name: 'AccountStore', description: 'Persistence port', methods: [{ name: 'save', signature: 'save(account)', description: 'x' }], implemented_by_module_ids: ['M3'] }]
  design.business_rules = [{ rule_id: 'BR1', title: 'Reject duplicate email', description: 'd', module_id: 'M2', pseudocode: null, grounding: 'EXPLICIT', requirement_ids: [], task_ids: [], rationale: null }]
  const model = buildClassDiagram(hld, design, 'C2')
  assert.equal(byId(model, 'IF1').shape, 'interface')
  assert.deepEqual(model.edges.find((e) => e.kind === 'impl'), { ...model.edges.find((e) => e.kind === 'impl'), source: 'M3', target: 'IF1', label: 'implements' })
  assert.ok(byId(model, 'M2').rows.some((r) => /Reject duplicate email/.test(r.text)))
})

test('detailed component diagram: modules and endpoints inside, HLD neighbours outside, connected through the right modules', () => {
  const model = buildDetailedComponentDiagram(hld, lld, 'C2')
  assert.deepEqual(model.nodes.filter((n) => n.group === 'C2').map((n) => n.id), ['M1', 'M2', 'M3'])
  assert.ok(byId(model, 'M1').rows.some((r) => /POST \/api\/register/.test(r.text)), 'the controller lists its endpoint')
  assert.deepEqual(model.nodes.filter((n) => !n.group).map((n) => [n.id, n.pin]).sort(), [['C1', 'first'], ['C3', 'last'], ['C4', 'last']].sort())
  const inbound = model.edges.find((e) => e.id === 'R1')
  assert.deepEqual([inbound.source, inbound.target], ['C1', 'M1'], 'callers enter through the controller')
  const toDb = model.edges.find((e) => e.id === 'R2')
  assert.deepEqual([toDb.source, toDb.target], ['M3', 'C3'], 'database access leaves from the repository')
})

test('detailed component diagram: the database component shows its tables', () => {
  const model = buildDetailedComponentDiagram(hld, lld, 'C3')
  assert.deepEqual(model.nodes.filter((n) => n.group === 'C3').map((n) => [n.id, n.shape]), [['TBL1', 'table']])
})

test('API interaction: callers, endpoints, request/response models and the module that handles each', () => {
  const model = buildApiDiagram(hld, lld, 'C2')
  assert.equal(model.direction, 'LR')
  assert.ok(byId(model, 'API1').title === 'POST /api/register')
  assert.deepEqual(model.edges.filter((e) => e.source === 'C1').map((e) => [e.target, e.label]), [['API1', 'HTTPS/JSON']])
  assert.ok(model.edges.some((e) => e.id === 'impl:API1' && e.target === 'M1'))
  assert.ok(model.edges.some((e) => e.id === 'req:API1') && model.edges.some((e) => e.id === 'res:API1'))
  assert.deepEqual(model.groups.map((g) => g.id), ['API:C2'])
  assert.match(buildApiDiagram(hld, lld, 'C3').empty, /no API endpoints/)
})

test('two endpoints handled by the same module do not create duplicate arrows or nodes', () => {
  const design = clone(lld)
  design.apis.push({ ...clone(design.apis[0]), api_id: 'API2', path: '/api/register/resend' })
  const model = buildApiDiagram(hld, design, 'C2')
  assert.equal(new Set(model.edges.map((e) => e.id)).size, model.edges.length)
  assert.equal(new Set(model.nodes.map((n) => n.id)).size, model.nodes.length)
  assert.equal(model.edges.filter((e) => e.source === 'M1' && e.target === 'M2').length, 1)
  assert.deepEqual(model.edges.filter((e) => e.kind === 'impl').map((e) => e.id).sort(), ['impl:API1', 'impl:API2'])
})

test('ER diagram: every table, key markers and foreign keys with crow\'s-foot ends', () => {
  const design = clone(lld)
  const first = design.tables[0]
  design.tables.push({ ...clone(first), table_id: 'TBL2', name: 'verification_codes', columns: [...clone(first.columns), { name: 'account_id', type: 'uuid', primary_key: false, nullable: false, unique: false, description: null }] })
  design.table_relationships = [{ relationship_id: 'TR1', source_table_id: 'TBL2', source_column: 'account_id', target_table_id: 'TBL1', target_column: 'id', cardinality: 'ONE_TO_MANY', description: null }]
  const model = buildErDiagram(design)
  assert.deepEqual(model.nodes.map((n) => n.id), ['TBL1', 'TBL2'])
  assert.ok(byId(model, 'TBL2').rows.some((r) => r.text === 'account_id' && r.tag === 'FK'))
  assert.ok(byId(model, 'TBL1').rows.some((r) => r.text === 'id' && r.tag === 'PK'))
  const [edge] = model.edges
  assert.deepEqual([edge.source, edge.target, edge.sourceEnd, edge.targetEnd], ['TBL2', 'TBL1', 'many', 'one'])
  assert.equal(edge.label, 'account_id → id')
  assert.match(buildErDiagram({ tables: [] }).empty, /no database tables/)
})

test('detailed sequence: participants resolved to components, modules or actors, with the API behind each call', () => {
  const model = buildLldSequence(hld, lld, 'SEQ1')
  assert.ok(model.participants.length >= 2 && model.messages.length >= 2)
  const kinds = new Set(model.participants.map((p) => p.kind))
  assert.ok([...kinds].every((k) => ['actor', 'component', 'module'].includes(k)))
  assert.ok(model.messages.every((m, i, all) => i === 0 || all[i - 1].order <= m.order))
  assert.ok(model.messages.some((m) => m.detail === 'POST /api/register'))
  assert.match(buildLldSequence(hld, { ...lld, sequence_flows: [] }, 'x').empty, /no sequence flows/)
})

// ------------------------------------------------- HLD <-> LLD traceability ----

test('every HLD component lists exactly its LLD modules, and every module points back at its component', () => {
  const index = buildIndex(hld, lld)
  hld.components.forEach((component) => {
    const detail = describeRef({ type: 'component', id: component.component_id }, hld, lld)
    assert.deepEqual(detail.links.map((l) => l.ref.id), lld.modules.filter((m) => m.component_id === component.component_id).map((m) => m.module_id))
  })
  lld.modules.forEach((module) => {
    const detail = describeRef({ type: 'module', id: module.module_id }, hld, lld)
    assert.deepEqual(detail.links.map((l) => l.ref), [{ type: 'component', id: module.component_id }])
    assert.equal(componentOf({ type: 'module', id: module.module_id }, index), module.component_id)
    assert.deepEqual(detail.actions[0].go, { level: 'HLD', componentId: module.component_id })
  })
  assert.deepEqual(describeRef({ type: 'component', id: 'C2' }, hld, lld).actions[0].go, { level: 'LLD', componentId: 'C2' })
  assert.equal(describeRef({ type: 'component', id: 'C1' }, hld, lld).actions.length, 0, 'no LLD to open for a component without modules')
})

test('describeRef covers every kind of element the diagrams can select and ignores unknown ids', () => {
  for (const ref of [
    { type: 'component', id: 'C2' }, { type: 'module', id: 'M1' }, { type: 'actor', id: 'A1' }, { type: 'deployment', id: 'DN2' },
    { type: 'table', id: 'TBL1' }, { type: 'api', id: 'API1' }, { type: 'integration', id: 'INT1' }, { type: 'system', id: 'SYSTEM' },
  ]) {
    const detail = describeRef(ref, hld, lld)
    assert.ok(detail && detail.title && detail.kind, `${ref.type} ${ref.id}`)
  }
  assert.equal(describeRef({ type: 'component', id: 'C99' }, hld, lld), null)
  assert.equal(describeRef(null, hld, lld), null)
})

test('drill-down choices only list components that have something to show', () => {
  assert.deepEqual(componentsWith(hld, lld, 'modules').map((c) => c.component_id), ['C2'])
  assert.deepEqual(componentsWith(hld, lld, 'apis').map((c) => c.component_id), ['C2'])
})

// ------------------------------------------------------ whole pipeline ----

test('every model lays out without overlaps and every node has a finite size', () => {
  const models = [
    buildContextDiagram(hld, 'X'), buildComponentDiagram(hld, lld, 'X'), buildDataFlowDiagram(hld, 'DF1', lld), buildDeploymentDiagram(hld, lld),
    buildClassDiagram(hld, lld, 'C2'), buildDetailedComponentDiagram(hld, lld, 'C2'), buildApiDiagram(hld, lld, 'C2'), buildErDiagram(lld),
  ]
  models.forEach((model) => {
    assert.ok(model.nodes.length > 0)
    assert.ok(model.nodes.every((n) => Number.isFinite(n.w) && Number.isFinite(n.h) && n.w > 0 && n.h > 0))
    const result = layoutCompound({ nodes: model.nodes, edges: model.edges, groups: model.groups }, { direction: model.direction })
    const boxes = model.nodes.map((n) => result.positions[n.id])
    assert.ok(boxes.every(Boolean))
    for (let i = 0; i < boxes.length; i += 1) for (let j = i + 1; j < boxes.length; j += 1) {
      const a = boxes[i]
      const b = boxes[j]
      assert.equal(a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h, false, `${model.nodes[i].id} overlaps ${model.nodes[j].id}`)
    }
  })
})

test('on the component diagram the actor is above the boundary and the external system below it', () => {
  const model = buildComponentDiagram(hld, lld, 'X')
  const result = layoutCompound({ nodes: model.nodes, edges: model.edges, groups: model.groups }, { direction: 'TB' })
  const boundary = result.groups.BOUNDARY
  assert.ok(result.positions['ACTOR:A1'].y + result.positions['ACTOR:A1'].h <= boundary.y)
  assert.ok(result.positions.C4.y >= boundary.y + boundary.h)
})
