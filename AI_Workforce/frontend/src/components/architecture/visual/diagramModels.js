// Turns the validated Architect output (HLD + LLD) into diagram models.
//
// Nothing here is hard-coded: every node, arrow, label and group comes from the design's own
// components, relationships, actors, deployment nodes, modules, APIs, tables and sequence flows.
// All functions are pure, so they are tested with `node --test` without a browser.
//
// A graph model is { direction, nodes, edges, groups, notes, empty }. A sequence model is
// { participants, messages, notes, empty }. Node `ref` objects ({ type, id }) are the shared
// vocabulary for selection: they carry the design's own ids (C2, M1, TBL1, API3 ...), which is
// how an HLD component is tied to its LLD modules and back.

export const pretty = (value) => String(value ?? '').replace(/_/g, ' ')
const TYPE_TAG = { FRONTEND: 'UI', API: 'API', SERVICE: 'SVC', GATEWAY: 'GW', AI_SERVICE: 'AI', DATABASE: 'DB', STORAGE: 'STORE', CACHE: 'CACHE', QUEUE: 'QUEUE', EXTERNAL_SYSTEM: 'EXT', OTHER: '' }
export const typeTag = (type) => TYPE_TAG[type] ?? pretty(type).slice(0, 4).toUpperCase()
export const clip = (text, max) => {
  const value = String(text ?? '')
  return value.length > max ? `${value.slice(0, Math.max(max - 1, 1))}…` : value
}
const approxWidth = (text, size = 12) => String(text ?? '').length * size * 0.56
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

export const SHAPE_BY_TYPE = {
  FRONTEND: 'frontend', API: 'box', SERVICE: 'box', GATEWAY: 'box', AI_SERVICE: 'ai', DATABASE: 'database',
  STORAGE: 'storage', CACHE: 'cache', QUEUE: 'queue', EXTERNAL_SYSTEM: 'cloud', OTHER: 'box',
}
const INTERACTION_LABEL = { HTTP: 'HTTP', MESSAGE: 'Message', DATABASE: 'Database', FUNCTION_CALL: 'Call', EVENT: 'Event', FILE: 'File', OTHER: '' }

/** Label for a component relationship: its stated protocol, else the interaction kind. */
export const relationshipLabel = (relationship) => relationship.protocol || INTERACTION_LABEL[relationship.interaction] || ''

// ---------------------------------------------------------------------------
// Index of the design: ids, parents and children. Drives HLD <-> LLD traceability.
// ---------------------------------------------------------------------------

export function buildIndex(hld = {}, lld = {}) {
  const components = hld.components || []
  const modules = lld.modules || []
  const index = {
    components,
    componentById: Object.fromEntries(components.map((c) => [c.component_id, c])),
    modules,
    moduleById: Object.fromEntries(modules.map((m) => [m.module_id, m])),
    modulesByComponent: {},
    apisByComponent: {},
    apisByModule: {},
    tableById: Object.fromEntries((lld.tables || []).map((t) => [t.table_id, t])),
    actorById: Object.fromEntries((hld.actors || []).map((a) => [a.actor_id, a])),
    deploymentById: Object.fromEntries((hld.deployment || []).map((d) => [d.node_id, d])),
    nodeOfComponent: {},
    interfacesByModule: {},
  }
  modules.forEach((m) => { (index.modulesByComponent[m.component_id] ||= []).push(m) })
  ;(lld.apis || []).forEach((api) => {
    ;(index.apisByComponent[api.component_id] ||= []).push(api)
    if (api.module_id) (index.apisByModule[api.module_id] ||= []).push(api)
  })
  ;(hld.deployment || []).forEach((node) => (node.component_ids || []).forEach((id) => { index.nodeOfComponent[id] = node.node_id }))
  ;(lld.interfaces || []).forEach((iface) => (iface.implemented_by_module_ids || []).forEach((id) => { (index.interfacesByModule[id] ||= []).push(iface) }))
  return index
}

/** The HLD component a selection belongs to (a module's parent, or the component itself). */
export function componentOf(ref, index) {
  if (!ref) return null
  if (ref.type === 'component') return ref.id
  if (ref.type === 'module') return index.moduleById[ref.id]?.component_id || null
  if (ref.type === 'api') return index.apisByComponent && Object.entries(index.apisByComponent).find(([, list]) => list.some((a) => a.api_id === ref.id))?.[0] || null
  return null
}

// ---------------------------------------------------------------------------
// Node sizing
// ---------------------------------------------------------------------------

function sizeNode(node) {
  const rows = node.rows || []
  const widest = Math.max(
    approxWidth(node.title, 13),
    approxWidth(node.subtitle, 10.5),
    ...rows.map((row) => approxWidth(row.text, row.mono ? 10.5 : 11) + (row.tag ? 34 : 0) + (row.right ? approxWidth(row.right, 9.5) + 12 : 0)),
  )
  const body = rows.length * 17
  const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
  switch (node.shape) {
    case 'actor': return { w: clamp(widest + 20, 100, 170), h: 100 }
    case 'system': return { w: clamp(widest + 44, 230, 330), h: 74 + body }
    case 'database': case 'storage': case 'cache': return { w: clamp(widest + 36, 150, 240), h: 82 + body }
    case 'cloud': return { w: clamp(widest + 44, 160, 240), h: 78 + body }
    case 'ai': return { w: clamp(widest + 56, 190, 270), h: 84 + body }
    case 'queue': return { w: clamp(widest + 44, 160, 240), h: 66 + body }
    case 'frontend': return { w: clamp(widest + 36, 170, 260), h: 74 + body }
    case 'node': return { w: clamp(widest + 36, 200, 290), h: 66 + body }
    case 'class': case 'interface': return { w: clamp(widest + 30, 180, 320), h: 48 + body + (rows.length ? 8 : 0) }
    case 'endpoint': return { w: clamp(widest + 36, 190, 300), h: node.subtitle ? 48 : 34 }
    case 'model': return { w: clamp(widest + 30, 170, 280), h: 48 + body + (rows.length ? 8 : 0) }
    case 'table': return { w: clamp(widest + 30, 200, 320), h: 40 + body + 8 }
    default: return { w: clamp(widest + 34, 160, 270), h: 62 + body }
  }
}

// Ids identify elements (selection, highlighting, React keys), so a builder that reaches the same
// element twice (two endpoints handled by one module, say) must not draw it twice.
const firstOfEach = (items) => {
  const seen = new Set()
  return items.filter((item) => (seen.has(item.id) ? false : seen.add(item.id)))
}

function finish(model) {
  const nodes = firstOfEach(model.nodes)
  nodes.forEach((node) => Object.assign(node, sizeNode(node)))
  // Endpoints stacked in one API surface read better at one width.
  const endpoints = nodes.filter((node) => node.shape === 'endpoint')
  const widest = Math.max(0, ...endpoints.map((node) => node.w))
  endpoints.forEach((node) => { node.w = widest })
  return { direction: 'TB', groups: [], notes: [], empty: null, ...model, nodes, edges: firstOfEach(model.edges) }
}

const componentNode = (component, index, extra = {}) => {
  const modules = index.modulesByComponent[component.component_id] || []
  return {
    id: component.component_id,
    shape: SHAPE_BY_TYPE[component.type] || 'box',
    tone: component.type,
    title: component.name,
    subtitle: [pretty(component.type), component.technology].filter(Boolean).join(' · '),
    rows: modules.length ? [{ text: plural(modules.length, 'LLD module'), muted: true }] : [],
    tooltip: `${component.component_id} · ${component.name}\n${component.description || ''}`.trim(),
    ref: { type: 'component', id: component.component_id },
    grounding: component.grounding,
    ...extra,
  }
}

const actorNode = (actor) => ({
  id: `ACTOR:${actor.actor_id}`,
  shape: 'actor',
  tone: 'ACTOR',
  title: actor.name,
  subtitle: actor.actor_id,
  tooltip: `${actor.name}\n${actor.description || ''}${actor.interaction ? `\n${actor.interaction}` : ''}`.trim(),
  ref: { type: 'actor', id: actor.actor_id },
  grounding: actor.grounding,
  pin: 'first',
})

// ---------------------------------------------------------------------------
// HLD diagrams
// ---------------------------------------------------------------------------

/** A. System context: the system as one box, the people who use it and the outside systems it uses. */
export function buildContextDiagram(hld, projectName) {
  const index = buildIndex(hld, {})
  const internal = index.components.filter((c) => c.type !== 'EXTERNAL_SYSTEM')
  const external = index.components.filter((c) => c.type === 'EXTERNAL_SYSTEM')
  const nodes = []
  const edges = []

  nodes.push({
    id: 'SYSTEM',
    shape: 'system',
    tone: 'SYSTEM',
    title: projectName || 'The system',
    subtitle: hld.style?.name || 'System under design',
    rows: [
      ...internal.slice(0, 6).map((c) => ({ text: c.name, tag: typeTag(c.type) })),
      ...(internal.length > 6 ? [{ text: `+${internal.length - 6} more components`, muted: true }] : []),
    ],
    tooltip: hld.overview || '',
    ref: { type: 'system', id: 'SYSTEM' },
  })

  ;(hld.actors || []).forEach((actor) => {
    nodes.push(actorNode(actor))
    edges.push({ id: `ctx:${actor.actor_id}`, source: `ACTOR:${actor.actor_id}`, target: 'SYSTEM', label: clip(actor.interaction || '', 30), tooltip: actor.description, kind: 'call' })
  })

  const nameKey = (value) => String(value || '').trim().toLowerCase()
  const externalByName = Object.fromEntries(external.map((c) => [nameKey(c.name), c]))
  // An integration is the same thing as an external component when the names match, or when the
  // component the integration belongs to already has a relationship with that external component.
  const integrationFor = (component) => (hld.integrations || []).find((i) => nameKey(i.name) === nameKey(component.name)
    || (i.component_id && (hld.relationships || []).some((r) => (
      (r.source_component_id === i.component_id && r.target_component_id === component.component_id)
      || (r.target_component_id === i.component_id && r.source_component_id === component.component_id)))))
  const representedIntegrations = new Set(external.map((c) => integrationFor(c)?.integration_id).filter(Boolean))
  const merged = {}
  const connect = (from, to, label, tooltip) => {
    const key = `${from}>${to}`
    merged[key] ||= { id: `ctx:${key}`, source: from, target: to, labels: [], tips: [], kind: 'call' }
    if (label && !merged[key].labels.includes(label)) merged[key].labels.push(label)
    if (tooltip) merged[key].tips.push(tooltip)
  }
  external.forEach((component) => {
    nodes.push(componentNode(component, index, { pin: 'last', rows: [] }))
    const related = (hld.relationships || []).filter((r) => r.source_component_id === component.component_id || r.target_component_id === component.component_id)
    const integration = integrationFor(component)
    related.forEach((r) => {
      const outgoing = r.target_component_id === component.component_id
      connect(outgoing ? 'SYSTEM' : component.component_id, outgoing ? component.component_id : 'SYSTEM', relationshipLabel(r) || integration?.protocol || '', r.description)
    })
    if (!related.length) connect('SYSTEM', component.component_id, integration?.protocol || '', '')
  })
  ;(hld.integrations || []).forEach((integration) => {
    if (externalByName[nameKey(integration.name)] || representedIntegrations.has(integration.integration_id)) return
    const id = `INT:${integration.integration_id}`
    nodes.push({ id, shape: 'cloud', tone: 'EXTERNAL_SYSTEM', title: integration.name, subtitle: 'External integration', rows: [], tooltip: integration.purpose, ref: { type: 'integration', id: integration.integration_id }, grounding: integration.grounding, pin: 'last' })
    connect('SYSTEM', id, integration.protocol || '', integration.purpose)
  })
  Object.values(merged).forEach((edge) => edges.push({ ...edge, label: clip(edge.labels.join(' · '), 34), tooltip: edge.tips.join('\n') }))

  const notes = []
  if (!(hld.actors || []).length) notes.push('This design names no actors (the people or outside systems that use the system). Regenerate the architecture to include them.')
  return finish({ direction: 'TB', nodes, edges, notes })
}

/** B. High-level component architecture: components inside the system boundary, actors above, external systems below. */
export function buildComponentDiagram(hld, lld, projectName) {
  const index = buildIndex(hld, lld)
  const nodes = []
  const edges = []
  ;(hld.actors || []).forEach((actor) => {
    nodes.push(actorNode(actor))
    ;(actor.component_ids || []).forEach((id) => {
      if (index.componentById[id]) edges.push({ id: `act:${actor.actor_id}>${id}`, source: `ACTOR:${actor.actor_id}`, target: id, label: clip(actor.interaction || '', 26), tooltip: actor.description, kind: 'call' })
    })
  })
  index.components.forEach((component) => {
    const external = component.type === 'EXTERNAL_SYSTEM'
    nodes.push(componentNode(component, index, external ? { pin: 'last', rows: [] } : { group: 'BOUNDARY' }))
  })
  ;(hld.relationships || []).forEach((r) => {
    if (!index.componentById[r.source_component_id] || !index.componentById[r.target_component_id]) return
    edges.push({
      id: r.relationship_id,
      source: r.source_component_id,
      target: r.target_component_id,
      label: clip(relationshipLabel(r), 22),
      tooltip: [r.description, r.data_exchanged ? `Data: ${r.data_exchanged}` : ''].filter(Boolean).join('\n'),
      kind: 'call',
    })
  })
  const notes = []
  if (!(hld.actors || []).length) notes.push('No actors in this design; regenerate the architecture to show who uses the system.')
  return finish({
    direction: 'TB',
    nodes,
    edges,
    groups: [{ id: 'BOUNDARY', label: `System boundary${projectName ? ` — ${projectName}` : ''}`, tone: 'SYSTEM' }],
    notes,
  })
}

/** C. Data flow: the components one flow passes through, with its numbered steps as arrows. */
export function buildDataFlowDiagram(hld, flowId, lld = {}) {
  const index = buildIndex(hld, lld)
  const flow = (hld.data_flows || []).find((f) => f.flow_id === flowId) || (hld.data_flows || [])[0]
  if (!flow) return finish({ nodes: [], edges: [], empty: 'This design defines no data flows.' })
  const steps = [...flow.steps].sort((a, b) => a.order - b.order)
  const ids = []
  steps.forEach((s) => [s.source_component_id, s.target_component_id].forEach((id) => { if (index.componentById[id] && !ids.includes(id)) ids.push(id) }))
  const nodes = ids.map((id) => componentNode(index.componentById[id], index, { rows: [] }))
  const edges = steps
    .filter((s) => index.componentById[s.source_component_id] && index.componentById[s.target_component_id])
    .map((s) => ({
      id: `${flow.flow_id}:${s.order}`,
      source: s.source_component_id,
      target: s.target_component_id,
      label: `${s.order}. ${clip(s.description, 30)}`,
      tooltip: `Step ${s.order}: ${s.description}`,
      kind: 'flow',
      seq: s.order,
    }))
  return finish({ direction: 'LR', nodes, edges, notes: [flow.description].filter(Boolean), flow })
}

/** D. Deployment: where the components run, and the links between those places. */
export function buildDeploymentDiagram(hld, lld = {}) {
  const index = buildIndex(hld, lld)
  const deployment = hld.deployment || []
  if (!deployment.length) {
    return finish({ nodes: [], edges: [], empty: 'This design has no structured deployment information. Regenerate the architecture to include it.', fallback: (hld.quality_considerations || []).filter((q) => q.category === 'DEPLOYMENT') })
  }
  const nodes = deployment.map((node) => ({
    id: node.node_id,
    shape: 'node',
    tone: node.kind,
    variant: node.kind,
    title: node.name,
    subtitle: [pretty(node.kind), node.technology].filter(Boolean).join(' · '),
    rows: (node.component_ids || []).filter((id) => index.componentById[id]).map((id) => ({ text: index.componentById[id].name, tag: typeTag(index.componentById[id].type), ref: { type: 'component', id } })),
    tooltip: `${node.node_id} · ${node.name}\n${node.description || ''}`.trim(),
    ref: { type: 'deployment', id: node.node_id },
    grounding: node.grounding,
  }))
  const externals = index.components.filter((c) => c.type === 'EXTERNAL_SYSTEM')
  externals.forEach((component) => nodes.push(componentNode(component, index, { pin: 'last', rows: [] })))
  const hostOf = (id) => index.nodeOfComponent[id] || (index.componentById[id]?.type === 'EXTERNAL_SYSTEM' ? id : null)
  const merged = {}
  ;(hld.relationships || []).forEach((r) => {
    const from = hostOf(r.source_component_id)
    const to = hostOf(r.target_component_id)
    if (!from || !to || from === to) return
    const key = `${from}>${to}`
    merged[key] ||= { id: `dep:${key}`, source: from, target: to, labels: [], kind: 'call' }
    const label = relationshipLabel(r)
    if (label && !merged[key].labels.includes(label)) merged[key].labels.push(label)
  })
  const edges = Object.values(merged).map((e) => ({ ...e, label: clip(e.labels.join(' · '), 30), tooltip: e.labels.join(', ') }))
  const unplaced = index.components.filter((c) => c.type !== 'EXTERNAL_SYSTEM' && !index.nodeOfComponent[c.component_id])
  const notes = unplaced.length ? [`Not placed on any deployment node: ${unplaced.map((c) => c.name).join(', ')}.`] : []
  return finish({ direction: 'LR', nodes, edges, notes })
}

/** E. High-level sequence: one data flow as lifelines (components, and the actor who starts it) and messages. */
export function buildHldSequence(hld, flowId, lld = {}) {
  const index = buildIndex(hld, lld)
  const flow = (hld.data_flows || []).find((f) => f.flow_id === flowId) || (hld.data_flows || [])[0]
  if (!flow) return { participants: [], messages: [], notes: [], empty: 'This design defines no data flows.' }
  const steps = [...flow.steps].sort((a, b) => a.order - b.order).filter((s) => index.componentById[s.source_component_id] && index.componentById[s.target_component_id])
  const participants = []
  const add = (participant) => { if (!participants.some((p) => p.id === participant.id)) participants.push(participant) }
  const messages = []
  const starter = steps.length && (hld.actors || []).find((a) => (a.component_ids || []).includes(steps[0].source_component_id))
  if (starter) {
    add({ id: `ACTOR:${starter.actor_id}`, label: starter.name, sublabel: 'Actor', tone: 'ACTOR', kind: 'actor', ref: { type: 'actor', id: starter.actor_id } })
    add(participantForComponent(index.componentById[steps[0].source_component_id]))
    messages.push({ id: 'start', order: 0, from: `ACTOR:${starter.actor_id}`, to: steps[0].source_component_id, label: clip(starter.interaction || 'uses', 44), tooltip: starter.description })
  }
  steps.forEach((s) => {
    add(participantForComponent(index.componentById[s.source_component_id]))
    add(participantForComponent(index.componentById[s.target_component_id]))
    messages.push({ id: `${flow.flow_id}:${s.order}`, order: s.order, from: s.source_component_id, to: s.target_component_id, label: clip(s.description, 48), tooltip: s.description })
  })
  return { participants, messages, notes: [flow.description].filter(Boolean), empty: null, flow }
}

const participantForComponent = (component) => ({
  id: component.component_id,
  label: component.name,
  sublabel: [pretty(component.type), component.technology].filter(Boolean).join(' · '),
  tone: component.type,
  kind: 'component',
  ref: { type: 'component', id: component.component_id },
})

// ---------------------------------------------------------------------------
// LLD diagrams
// ---------------------------------------------------------------------------

/** Components that have something to show in a drill-down view. */
export const componentsWith = (hld, lld, what) => {
  const index = buildIndex(hld, lld)
  const keep = {
    modules: (id) => (index.modulesByComponent[id] || []).length,
    apis: (id) => (index.apisByComponent[id] || []).length,
  }[what]
  return index.components.filter((c) => keep(c.component_id))
}

const moduleNode = (module, index, extra = {}) => {
  const component = index.componentById[module.component_id]
  const methods = module.methods || []
  const rules = (extra.rules || [])
  return {
    id: module.module_id,
    shape: 'class',
    tone: module.kind,
    stereotype: pretty(module.kind).toLowerCase(),
    title: module.name,
    subtitle: `«${pretty(module.kind).toLowerCase()}» ${module.module_id}`,
    rows: [
      ...methods.slice(0, 6).map((m) => ({ text: clip(m.signature || m.name, 44), mono: true })),
      ...(methods.length > 6 ? [{ text: `+${methods.length - 6} more methods`, muted: true }] : []),
      ...rules.slice(0, 2).map((r) => ({ text: `rule: ${clip(r.title, 32)}`, muted: true })),
    ],
    tooltip: `${module.module_id} · ${module.name} (${pretty(module.kind)})\nIn ${component?.component_id || module.component_id} ${component?.name || ''}\n${module.description || ''}`.trim(),
    ref: { type: 'module', id: module.module_id },
    grounding: module.grounding,
    ...extra.node,
  }
}

/** A. Class / module diagram of one component: classes, interfaces, dependencies and business rules. */
export function buildClassDiagram(hld, lld, componentId) {
  const index = buildIndex(hld, lld)
  const component = index.componentById[componentId]
  const own = index.modulesByComponent[componentId] || []
  if (!component || !own.length) return finish({ nodes: [], edges: [], empty: 'This component has no LLD modules.' })
  const ownIds = new Set(own.map((m) => m.module_id))
  const rulesOf = (id) => (lld.business_rules || []).filter((r) => r.module_id === id)
  const nodes = own.map((m) => moduleNode(m, index, { rules: rulesOf(m.module_id), node: { group: componentId } }))
  const edges = []

  const ghosts = new Set()
  const ghost = (module) => {
    if (ghosts.has(module.module_id)) return
    ghosts.add(module.module_id)
    const parent = index.componentById[module.component_id]
    nodes.push(moduleNode(module, index, { node: { ghost: true, rows: [], subtitle: `${module.module_id} · in ${parent?.name || module.component_id}` } }))
  }
  own.forEach((m) => (m.depends_on_module_ids || []).forEach((dep) => {
    const target = index.moduleById[dep]
    if (!target) return
    if (!ownIds.has(dep)) ghost(target)
    edges.push({ id: `dep:${m.module_id}>${dep}`, source: m.module_id, target: dep, label: '', tooltip: `${m.name} depends on ${target.name}`, kind: 'dep' })
  }))
  index.modules.filter((m) => !ownIds.has(m.module_id)).forEach((m) => {
    ;(m.depends_on_module_ids || []).filter((dep) => ownIds.has(dep)).forEach((dep) => {
      ghost(m)
      edges.push({ id: `dep:${m.module_id}>${dep}`, source: m.module_id, target: dep, label: '', tooltip: `${m.name} depends on ${index.moduleById[dep].name}`, kind: 'dep' })
    })
  })
  ;(lld.interfaces || []).filter((i) => (i.implemented_by_module_ids || []).some((id) => ownIds.has(id))).forEach((iface) => {
    nodes.push({
      id: iface.interface_id,
      shape: 'interface',
      tone: 'INTERFACE',
      title: iface.name,
      subtitle: `«interface» ${iface.interface_id}`,
      rows: (iface.methods || []).slice(0, 5).map((m) => ({ text: clip(m.signature || m.name, 44), mono: true })),
      tooltip: `${iface.name}\n${iface.description || ''}`,
      ref: { type: 'interface', id: iface.interface_id },
      group: componentId,
    })
    ;(iface.implemented_by_module_ids || []).filter((id) => ownIds.has(id)).forEach((id) => {
      edges.push({ id: `impl:${id}>${iface.interface_id}`, source: id, target: iface.interface_id, label: 'implements', tooltip: `${index.moduleById[id].name} implements ${iface.name}`, kind: 'impl' })
    })
  })
  return finish({
    direction: 'TB',
    nodes,
    edges,
    groups: [{ id: componentId, label: `${component.component_id} · ${component.name}`, sublabel: [pretty(component.type), component.technology].filter(Boolean).join(' · '), tone: component.type, ref: { type: 'component', id: componentId } }],
    notes: ghosts.size ? [`Faded boxes belong to other components that this one depends on or is used by.`] : [],
  })
}

/** B. Detailed component diagram: one component opened up (modules, endpoints, tables) with its HLD neighbours around it. */
export function buildDetailedComponentDiagram(hld, lld, componentId) {
  const index = buildIndex(hld, lld)
  const component = index.componentById[componentId]
  if (!component) return finish({ nodes: [], edges: [], empty: 'Select a component to open it up.' })
  const own = index.modulesByComponent[componentId] || []
  const tables = component.type === 'DATABASE' ? (lld.tables || []) : []
  const nodes = []
  const edges = []

  own.forEach((m) => {
    const endpoints = index.apisByModule[m.module_id] || []
    const rows = endpoints.length
      ? endpoints.slice(0, 6).map((api) => ({ text: `${api.method} ${api.path}`, mono: true, tag: api.auth_required ? '🔒' : undefined })).concat(endpoints.length > 6 ? [{ text: `+${endpoints.length - 6} more endpoints`, muted: true }] : [])
      : (m.responsibilities || []).slice(0, 2).map((text) => ({ text: clip(text, 40), muted: true }))
    nodes.push({ ...moduleNode(m, index, { node: { group: componentId, rows } }), shape: 'module' })
    ;(m.depends_on_module_ids || []).forEach((dep) => {
      if (index.moduleById[dep]?.component_id === componentId) edges.push({ id: `dep:${m.module_id}>${dep}`, source: m.module_id, target: dep, label: '', tooltip: `${m.name} uses ${index.moduleById[dep].name}`, kind: 'dep' })
    })
  })
  const looseEndpoints = (index.apisByComponent[componentId] || []).filter((api) => !api.module_id || !index.moduleById[api.module_id])
  looseEndpoints.forEach((api) => {
    nodes.push({ id: api.api_id, shape: 'endpoint', tone: api.method, title: `${api.method} ${api.path}`, subtitle: '', rows: [], tooltip: api.summary, ref: { type: 'api', id: api.api_id }, group: componentId })
  })
  tables.forEach((table) => {
    nodes.push({ id: table.table_id, shape: 'table', tone: 'TABLE', title: table.name, subtitle: '', rows: [{ text: plural(table.columns.length, 'column'), muted: true }], tooltip: table.description, ref: { type: 'table', id: table.table_id }, group: componentId })
  })
  if (!nodes.length) {
    nodes.push({ id: `${componentId}:self`, shape: 'class', tone: component.type, title: component.name, subtitle: 'No LLD modules for this component', rows: (component.responsibilities || []).slice(0, 4).map((text) => ({ text: clip(text, 40), muted: true })), tooltip: component.description, ref: { type: 'component', id: componentId }, group: componentId })
  }

  const inside = nodes.map((n) => n.id)
  // First module of the most preferred kind (the kinds are listed in order of preference).
  const kindOrder = (kinds) => {
    for (const kind of kinds) {
      const found = inside.find((id) => index.moduleById[id]?.kind === kind)
      if (found) return found
    }
    return inside[0]
  }
  const entry = kindOrder(['CONTROLLER', 'UI_COMPONENT', 'MIDDLEWARE', 'CLIENT'])
  const dataEdge = tables.length ? tables[0].table_id : kindOrder(['REPOSITORY', 'CLIENT', 'SERVICE'])
  const neighbours = {}
  ;(hld.relationships || []).forEach((r) => {
    if (r.target_component_id === componentId && index.componentById[r.source_component_id]) neighbours[r.source_component_id] = { incoming: r }
    if (r.source_component_id === componentId && index.componentById[r.target_component_id]) neighbours[r.target_component_id] = { ...(neighbours[r.target_component_id] || {}), outgoing: r }
  })
  Object.entries(neighbours).forEach(([id, link]) => {
    const other = index.componentById[id]
    nodes.push(componentNode(other, index, { rows: [], pin: link.incoming && !link.outgoing ? 'first' : link.outgoing && !link.incoming ? 'last' : undefined }))
    if (link.incoming) edges.push({ id: link.incoming.relationship_id, source: id, target: entry, label: clip(relationshipLabel(link.incoming), 18), tooltip: link.incoming.description, kind: 'call' })
    if (link.outgoing) edges.push({ id: link.outgoing.relationship_id, source: dataEdge, target: id, label: clip(relationshipLabel(link.outgoing), 18), tooltip: link.outgoing.description, kind: 'call' })
  })
  return finish({
    direction: 'TB',
    nodes,
    edges,
    groups: [{ id: componentId, label: `${component.component_id} · ${component.name}`, sublabel: [pretty(component.type), component.technology].filter(Boolean).join(' · '), tone: component.type, ref: { type: 'component', id: componentId } }],
  })
}

/** C. API interaction: who calls the component's endpoints, what each endpoint takes and returns, and what handles it. */
export function buildApiDiagram(hld, lld, componentId) {
  const index = buildIndex(hld, lld)
  const component = index.componentById[componentId]
  const apis = index.apisByComponent[componentId] || []
  if (!component || !apis.length) return finish({ nodes: [], edges: [], empty: 'This component exposes no API endpoints.' })
  const models = Object.fromEntries((lld.data_models || []).map((m) => [m.data_model_id, m]))
  const nodes = []
  const edges = []
  const seen = new Set()
  const addNode = (node) => { if (!seen.has(node.id)) { seen.add(node.id); nodes.push(node) } }

  apis.forEach((api) => addNode({
    id: api.api_id,
    shape: 'endpoint',
    tone: api.method,
    title: `${api.method} ${api.path}`,
    subtitle: clip(api.summary, 40),
    rows: [],
    tag: api.auth_required ? '🔒' : '',
    tooltip: `${api.api_id} · ${api.summary}${api.auth_required ? '\nAuthentication required' : ''}${(api.errors || []).length ? `\nErrors: ${api.errors.map((e) => e.status_code).join(', ')}` : ''}`,
    ref: { type: 'api', id: api.api_id },
    group: `API:${componentId}`,
  }))

  const consumers = (hld.relationships || []).filter((r) => r.target_component_id === componentId && index.componentById[r.source_component_id])
  consumers.forEach((r) => {
    addNode(componentNode(index.componentById[r.source_component_id], index, { rows: [], pin: 'first' }))
    edges.push({ id: `call:${r.relationship_id}`, source: r.source_component_id, target: apis[0].api_id, label: clip(relationshipLabel(r), 20), tooltip: `${r.description}\nCalls the ${component.name} endpoints`, kind: 'call' })
  })

  apis.forEach((api) => {
    ;[['request', api.request_model_id], ['response', api.response_model_id]].forEach(([role, id]) => {
      const model = models[id]
      if (!model) return
      addNode({
        id: model.data_model_id,
        shape: 'model',
        tone: model.kind,
        title: model.name,
        subtitle: `«${String(model.kind).toLowerCase()}» ${model.data_model_id}`,
        rows: (model.fields || []).slice(0, 5).map((f) => ({ text: f.name, right: f.type, tag: f.required ? '*' : '' })).concat((model.fields || []).length > 5 ? [{ text: `+${model.fields.length - 5} more fields`, muted: true }] : []),
        tooltip: model.description,
        ref: { type: 'model', id: model.data_model_id },
      })
      edges.push(role === 'request'
        ? { id: `req:${api.api_id}`, source: model.data_model_id, target: api.api_id, label: 'request', tooltip: `${api.method} ${api.path} accepts ${model.name}`, kind: 'dep' }
        : { id: `res:${api.api_id}`, source: api.api_id, target: model.data_model_id, label: 'response', tooltip: `${api.method} ${api.path} returns ${model.name}`, kind: 'dep' })
    })
    const handler = api.module_id && index.moduleById[api.module_id]
    if (handler) {
      addNode(moduleNode(handler, index, { node: { rows: [] } }))
      edges.push({ id: `impl:${api.api_id}`, source: api.api_id, target: handler.module_id, label: 'handled by', tooltip: `${api.path} is implemented by ${handler.name}`, kind: 'impl' })
      ;(handler.depends_on_module_ids || []).forEach((dep) => {
        const next = index.moduleById[dep]
        if (!next) return
        addNode(moduleNode(next, index, { node: { rows: [] } }))
        edges.push({ id: `dep:${handler.module_id}>${dep}`, source: handler.module_id, target: dep, label: 'uses', tooltip: `${handler.name} uses ${next.name}`, kind: 'dep' })
      })
    }
  })
  return finish({
    direction: 'LR',
    nodes,
    edges,
    groups: [{ id: `API:${componentId}`, label: `${component.name} — API surface`, sublabel: `${plural(apis.length, 'endpoint')}`, tone: component.type, direction: 'LR', ref: { type: 'component', id: componentId } }],
  })
}

/** D. Database ER diagram from the tables and their foreign keys. */
export function buildErDiagram(lld) {
  const tables = lld.tables || []
  if (!tables.length) return finish({ nodes: [], edges: [], empty: 'This design defines no database tables.' })
  const foreignKeys = new Set((lld.table_relationships || []).map((r) => `${r.source_table_id}.${r.source_column}`))
  const nodes = tables.map((table) => {
    const columns = table.columns || []
    const shown = columns.slice(0, 12)
    return {
      id: table.table_id,
      shape: 'table',
      tone: 'TABLE',
      title: table.name,
      subtitle: '',
      rows: [
        ...shown.map((c) => ({
          text: c.name,
          right: c.type,
          tag: c.primary_key ? 'PK' : foreignKeys.has(`${table.table_id}.${c.name}`) ? 'FK' : c.unique ? 'UQ' : '',
          muted: c.nullable && !c.primary_key,
        })),
        ...(columns.length > shown.length ? [{ text: `+${columns.length - shown.length} more columns`, muted: true }] : []),
      ],
      tooltip: `${table.table_id} · ${table.name}\n${table.description || ''}`.trim(),
      ref: { type: 'table', id: table.table_id },
      grounding: table.grounding,
    }
  })
  // Cardinality is read from the referenced (target) table to the referencing (source) table.
  const ends = { ONE_TO_MANY: ['many', 'one'], ONE_TO_ONE: ['one', 'one'], MANY_TO_MANY: ['many', 'many'] }
  const edges = (lld.table_relationships || []).map((r) => {
    const [sourceEnd, targetEnd] = ends[r.cardinality] || ['none', 'none']
    return {
      id: r.relationship_id,
      source: r.source_table_id,
      target: r.target_table_id,
      label: `${r.source_column} → ${r.target_column}`,
      tooltip: `${r.source_table_id}.${r.source_column} references ${r.target_table_id}.${r.target_column} (${pretty(r.cardinality).toLowerCase()})${r.description ? `\n${r.description}` : ''}`,
      kind: 'fk',
      sourceEnd,
      targetEnd,
    }
  })
  return finish({ direction: 'LR', nodes, edges })
}

/** E. Detailed sequence diagram of one LLD sequence flow. */
export function buildLldSequence(hld, lld, flowId) {
  const index = buildIndex(hld, lld)
  const flow = (lld.sequence_flows || []).find((f) => f.sequence_id === flowId) || (lld.sequence_flows || [])[0]
  if (!flow) return { participants: [], messages: [], notes: [], empty: 'This design defines no sequence flows.' }
  const apiById = Object.fromEntries((lld.apis || []).map((a) => [a.api_id, a]))
  const participants = flow.participants.map((p) => {
    const module = p.ref_id && index.moduleById[p.ref_id]
    const component = p.ref_id && index.componentById[p.ref_id]
    if (module) return { id: p.participant_id, label: p.label, sublabel: `«${pretty(module.kind).toLowerCase()}» ${module.module_id}`, tone: module.kind, kind: 'module', ref: { type: 'module', id: module.module_id } }
    if (component) return { id: p.participant_id, label: p.label, sublabel: `${pretty(component.type)} · ${component.component_id}`, tone: component.type, kind: 'component', ref: { type: 'component', id: component.component_id } }
    return { id: p.participant_id, label: p.label, sublabel: 'Actor', tone: 'ACTOR', kind: 'actor', ref: null }
  })
  const ids = new Set(participants.map((p) => p.id))
  const messages = [...flow.steps].sort((a, b) => a.order - b.order)
    .filter((s) => ids.has(s.source_participant_id) && ids.has(s.target_participant_id))
    .map((s) => {
      const api = s.api_id && apiById[s.api_id]
      return { id: `${flow.sequence_id}:${s.order}`, order: s.order, from: s.source_participant_id, to: s.target_participant_id, label: clip(s.message, 52), detail: api ? `${api.method} ${api.path}` : '', tooltip: `${s.message}${api ? `\n${api.method} ${api.path}` : ''}` }
    })
  return { participants, messages, notes: [flow.description].filter(Boolean), empty: null, flow }
}

// ---------------------------------------------------------------------------
// Selection details (HLD <-> LLD traceability)
// ---------------------------------------------------------------------------

/** What to show in the side panel for a selected element, including the links that cross HLD <-> LLD. */
export function describeRef(ref, hld, lld) {
  if (!ref) return null
  const index = buildIndex(hld, lld)
  const modulesLink = (modules) => modules.map((m) => ({ label: `${m.module_id} ${m.name}`, hint: pretty(m.kind), ref: { type: 'module', id: m.module_id } }))
  if (ref.type === 'component') {
    const c = index.componentById[ref.id]
    if (!c) return null
    const modules = index.modulesByComponent[ref.id] || []
    const apis = index.apisByComponent[ref.id] || []
    return {
      kind: 'Component', title: `${c.component_id} · ${c.name}`, level: 'HLD', grounding: c.grounding,
      facts: [['Type', pretty(c.type)], ['Technology', c.technology || '—'], ['Hosted on', index.deploymentById[index.nodeOfComponent[c.component_id]]?.name || '—']],
      text: c.description, bullets: (c.responsibilities || []).slice(0, 5),
      linksTitle: `LLD modules (${modules.length})`, links: modulesLink(modules),
      extra: apis.length ? [`${plural(apis.length, 'API endpoint')}`] : [],
      actions: modules.length || apis.length ? [{ label: 'Open in LLD', go: { level: 'LLD', componentId: ref.id } }] : [],
    }
  }
  if (ref.type === 'module') {
    const m = index.moduleById[ref.id]
    if (!m) return null
    const parent = index.componentById[m.component_id]
    const deps = (m.depends_on_module_ids || []).map((id) => index.moduleById[id]).filter(Boolean)
    const apis = index.apisByModule[m.module_id] || []
    return {
      kind: 'Module', title: `${m.module_id} · ${m.name}`, level: 'LLD', grounding: m.grounding,
      facts: [['Kind', pretty(m.kind)], ['Methods', String((m.methods || []).length)], ['Part of', parent ? `${parent.component_id} ${parent.name}` : m.component_id]],
      text: m.description, bullets: (m.responsibilities || []).slice(0, 5),
      linksTitle: 'Parent component (HLD)', links: parent ? [{ label: `${parent.component_id} ${parent.name}`, hint: pretty(parent.type), ref: { type: 'component', id: parent.component_id } }] : [],
      extra: [...(deps.length ? [`Depends on: ${deps.map((d) => d.name).join(', ')}`] : []), ...apis.map((a) => `${a.method} ${a.path}`)],
      actions: parent ? [{ label: 'Show in HLD', go: { level: 'HLD', componentId: parent.component_id } }] : [],
    }
  }
  if (ref.type === 'actor') {
    const a = index.actorById[ref.id]
    if (!a) return null
    return {
      kind: 'Actor', title: `${a.actor_id} · ${a.name}`, level: 'HLD', grounding: a.grounding, facts: [], text: a.description, bullets: a.interaction ? [a.interaction] : [],
      linksTitle: 'Uses components', links: (a.component_ids || []).filter((id) => index.componentById[id]).map((id) => ({ label: `${id} ${index.componentById[id].name}`, ref: { type: 'component', id } })), extra: [], actions: [],
    }
  }
  if (ref.type === 'deployment') {
    const d = index.deploymentById[ref.id]
    if (!d) return null
    return {
      kind: 'Deployment node', title: `${d.node_id} · ${d.name}`, level: 'HLD', grounding: d.grounding, facts: [['Kind', pretty(d.kind)], ['Technology', d.technology || '—']], text: d.description, bullets: [],
      linksTitle: 'Runs components', links: (d.component_ids || []).filter((id) => index.componentById[id]).map((id) => ({ label: `${id} ${index.componentById[id].name}`, ref: { type: 'component', id } })), extra: [], actions: [],
    }
  }
  if (ref.type === 'table') {
    const t = index.tableById[ref.id]
    if (!t) return null
    return { kind: 'Table', title: `${t.table_id} · ${t.name}`, level: 'LLD', grounding: t.grounding, facts: [['Columns', String(t.columns.length)], ['Primary key', t.columns.filter((c) => c.primary_key).map((c) => c.name).join(', ') || '—']], text: t.description, bullets: [], linksTitle: '', links: [], extra: [], actions: [] }
  }
  if (ref.type === 'api') {
    const a = (lld.apis || []).find((x) => x.api_id === ref.id)
    if (!a) return null
    const module = a.module_id && index.moduleById[a.module_id]
    const component = index.componentById[a.component_id]
    return {
      kind: 'API endpoint', title: `${a.method} ${a.path}`, level: 'LLD', grounding: a.grounding, facts: [['Auth', a.auth_required ? 'required' : 'none'], ['Component', component ? `${component.component_id} ${component.name}` : a.component_id]], text: a.summary, bullets: [],
      linksTitle: 'Implemented by', links: [...(module ? [{ label: `${module.module_id} ${module.name}`, ref: { type: 'module', id: module.module_id } }] : []), ...(component ? [{ label: `${component.component_id} ${component.name}`, ref: { type: 'component', id: component.component_id } }] : [])], extra: [], actions: [],
    }
  }
  if (ref.type === 'model') {
    const m = (lld.data_models || []).find((x) => x.data_model_id === ref.id)
    if (!m) return null
    return { kind: 'Data model', title: `${m.data_model_id} · ${m.name}`, level: 'LLD', grounding: m.grounding, facts: [['Kind', pretty(m.kind)], ['Fields', String((m.fields || []).length)]], text: m.description, bullets: [], linksTitle: '', links: [], extra: [], actions: [] }
  }
  if (ref.type === 'interface') {
    const i = (lld.interfaces || []).find((x) => x.interface_id === ref.id)
    if (!i) return null
    return { kind: 'Interface', title: `${i.interface_id} · ${i.name}`, level: 'LLD', facts: [['Methods', String((i.methods || []).length)]], text: i.description, bullets: [], linksTitle: 'Implemented by', links: modulesLink((i.implemented_by_module_ids || []).map((id) => index.moduleById[id]).filter(Boolean)), extra: [], actions: [] }
  }
  if (ref.type === 'system') return { kind: 'System', title: 'The system', level: 'HLD', facts: [], text: hld.overview, bullets: [], linksTitle: '', links: [], extra: [], actions: [] }
  if (ref.type === 'integration') {
    const i = (hld.integrations || []).find((x) => x.integration_id === ref.id)
    if (!i) return null
    return { kind: 'Integration', title: `${i.integration_id} · ${i.name}`, level: 'HLD', grounding: i.grounding, facts: [['Protocol', i.protocol || '—']], text: i.purpose, bullets: [], linksTitle: '', links: [], extra: [], actions: [] }
  }
  return null
}
