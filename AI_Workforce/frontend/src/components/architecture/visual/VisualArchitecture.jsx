import { useMemo, useState } from 'react'
import { ArrowRight, Link2, MousePointerClick } from 'lucide-react'
import GraphDiagram from './GraphDiagram'
import SequenceDiagram from './SequenceDiagram'
import {
  buildApiDiagram, buildClassDiagram, buildComponentDiagram, buildContextDiagram, buildDataFlowDiagram,
  buildDeploymentDiagram, buildDetailedComponentDiagram, buildErDiagram, buildHldSequence, buildIndex,
  buildLldSequence, componentOf, componentsWith, describeRef, pretty,
} from './diagramModels'

/**
 * Visual HLD and LLD diagrams, generated from the validated Architect output.
 *
 *   HLD answers "what are the building blocks and how do they talk?":
 *     system context, high-level architecture, data flow, deployment, sequence.
 *   LLD answers "how is each building block built inside?":
 *     class/module, component detail, API interaction, database ER, detailed sequence.
 *
 * Selecting an HLD component shows its LLD modules (and the other way round) using the design's
 * own component / module ids.
 */

const HLD_VIEWS = [
  { key: 'context', label: 'System Context' },
  { key: 'architecture', label: 'High-Level Architecture' },
  { key: 'dataflow', label: 'Data Flow' },
  { key: 'deployment', label: 'Deployment' },
  { key: 'sequence', label: 'Sequence' },
]
const LLD_VIEWS = [
  { key: 'class', label: 'Class / Module' },
  { key: 'detail', label: 'Component Detail' },
  { key: 'api', label: 'API Interaction' },
  { key: 'er', label: 'Database ER' },
  { key: 'sequence', label: 'Sequence' },
]
const BLURB = {
  HLD: 'The major building blocks of the system and how they communicate.',
  LLD: 'How each building block is designed inside: modules, classes, APIs, tables and interactions.',
}
const VIEW_HELP = {
  'HLD:context': 'Who uses the system and which outside systems it depends on.',
  'HLD:architecture': 'The components inside the system boundary, with actors above and external systems below.',
  'HLD:dataflow': 'The numbered steps of one data flow between components.',
  'HLD:deployment': 'Where the components run and how those places connect.',
  'HLD:sequence': 'One data flow over time, component by component.',
  'LLD:class': 'The modules (classes) of one component, their dependencies and interfaces.',
  'LLD:detail': 'One component opened up: its modules, endpoints and tables, with its HLD neighbours around it.',
  'LLD:api': 'Who calls the component\'s endpoints, what each takes and returns, and what handles it.',
  'LLD:er': 'The database tables, their keys and foreign-key relationships.',
  'LLD:sequence': 'One use case step by step across actors, components and modules.',
}

const chip = (active) => `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${active ? 'bg-primary text-white' : 'bg-bg-light text-text-secondary hover:text-text-primary'}`
const subChip = (active) => `px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${active ? 'bg-primary-light border-primary text-primary' : 'bg-white border-border-light text-text-secondary hover:text-text-primary'}`
const GROUND = { EXPLICIT: 'bg-green-100 text-green-800', INFERRED: 'bg-blue-100 text-blue-800', ASSUMED: 'bg-yellow-100 text-yellow-800', UNKNOWN: 'bg-gray-100 text-gray-700' }

function DetailPanel({ detail, actions, onPick, onGo }) {
  if (!detail) {
    return (
      <div className="border border-dashed border-border-light rounded-xl p-5 text-sm text-text-secondary flex flex-col items-start gap-2 bg-bg-light/50">
        <MousePointerClick className="w-5 h-5 text-primary" />
        <p className="font-medium text-text-primary">Select an element</p>
        <p>Click a component, module, table or endpoint to see its details and how it connects between the HLD and the LLD.</p>
      </div>
    )
  }
  return (
    <div className="border border-border-light rounded-xl p-4 bg-white space-y-3" data-testid="detail-panel">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-primary-light text-primary">{detail.level}</span>
        <span className="text-xs text-text-secondary">{detail.kind}</span>
        {detail.grounding && <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${GROUND[detail.grounding] || GROUND.UNKNOWN}`}>{detail.grounding}</span>}
      </div>
      <h4 className="font-semibold text-text-primary leading-snug break-words">{detail.title}</h4>
      {detail.text && <p className="text-sm text-text-secondary">{detail.text}</p>}
      {detail.facts.length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          {detail.facts.map(([label, value]) => (
            <div key={label} className="contents"><dt className="text-text-secondary">{label}</dt><dd className="text-text-primary break-words">{value}</dd></div>
          ))}
        </dl>
      )}
      {detail.bullets.length > 0 && <ul className="list-disc pl-4 text-xs text-text-secondary space-y-0.5">{detail.bullets.map((b) => <li key={b}>{b}</li>)}</ul>}
      {detail.extra.length > 0 && <ul className="text-xs text-text-secondary space-y-0.5">{detail.extra.map((line) => <li key={line}>{line}</li>)}</ul>}
      {detail.links.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-text-primary mb-1.5 flex items-center gap-1"><Link2 className="w-3.5 h-3.5 text-primary" />{detail.linksTitle}</p>
          <div className="flex flex-wrap gap-1.5">
            {detail.links.map((link) => (
              <button key={`${link.ref.type}:${link.ref.id}`} onClick={() => onPick(link.ref)} title={link.hint} className="px-2 py-1 rounded-md text-xs bg-bg-light hover:bg-primary-light text-text-primary border border-border-light text-left">
                {link.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {actions.map((action) => (
        <button key={action.label} onClick={() => onGo(action.go)} className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-primary text-white hover:bg-primary-dark transition-colors">
          {action.label}<ArrowRight className="w-4 h-4" />
        </button>
      ))}
    </div>
  )
}

function Empty({ model }) {
  return (
    <div className="border border-dashed border-border-light rounded-xl bg-bg-light/50 p-8 text-center text-sm text-text-secondary" data-testid="diagram-empty">
      <p>{model.empty}</p>
      {model.fallback?.length > 0 && (
        <div className="mt-4 text-left max-w-2xl mx-auto space-y-2">
          <p className="font-medium text-text-primary">Deployment notes from the design</p>
          {model.fallback.map((item) => (
            <div key={item.consideration_id} className="bg-white border border-border-light rounded-lg p-3"><p className="font-medium text-text-primary text-sm">{item.title || item.consideration_id}</p><p className="text-xs mt-1">{item.approach}</p></div>
          ))}
        </div>
      )}
    </div>
  )
}

function VisualArchitecture({ hld, lld, projectName }) {
  const [level, setLevel] = useState('HLD')
  const [hldView, setHldView] = useState('architecture')
  const [lldView, setLldView] = useState('class')
  const [hldFlow, setHldFlow] = useState(null)
  const [lldFlow, setLldFlow] = useState(null)
  const [focus, setFocus] = useState(null)
  const [selected, setSelected] = useState(null)

  const index = useMemo(() => buildIndex(hld, lld), [hld, lld])
  const view = level === 'HLD' ? hldView : lldView
  const hldFlows = hld?.data_flows || []
  const lldFlows = lld?.sequence_flows || []

  const focusOptions = useMemo(() => {
    if (level !== 'LLD') return []
    if (lldView === 'class') return componentsWith(hld, lld, 'modules')
    if (lldView === 'api') return componentsWith(hld, lld, 'apis')
    if (lldView === 'detail') return index.components.filter((c) => c.type !== 'EXTERNAL_SYSTEM')
    return []
  }, [level, lldView, hld, lld, index])
  // Open on a component that has something to show: the first with modules or endpoints, else the first.
  const richest = focusOptions.find((c) => (index.modulesByComponent[c.component_id] || []).length || (index.apisByComponent[c.component_id] || []).length)
  const focusId = focusOptions.some((c) => c.component_id === focus) ? focus : (richest || focusOptions[0])?.component_id

  const model = useMemo(() => {
    if (level === 'HLD') {
      if (hldView === 'context') return buildContextDiagram(hld, projectName)
      if (hldView === 'architecture') return buildComponentDiagram(hld, lld, projectName)
      if (hldView === 'dataflow') return buildDataFlowDiagram(hld, hldFlow, lld)
      if (hldView === 'deployment') return buildDeploymentDiagram(hld, lld)
      return buildHldSequence(hld, hldFlow, lld)
    }
    if (lldView === 'class') return buildClassDiagram(hld, lld, focusId)
    if (lldView === 'detail') return buildDetailedComponentDiagram(hld, lld, focusId)
    if (lldView === 'api') return buildApiDiagram(hld, lld, focusId)
    if (lldView === 'er') return buildErDiagram(lld)
    return buildLldSequence(hld, lld, lldFlow)
  }, [level, hldView, lldView, hldFlow, lldFlow, focusId, hld, lld, projectName])

  // What the diagram marks as selected. On HLD diagrams a selected module shows its parent component.
  const parentId = componentOf(selected, index)
  const canvasSelected = !selected ? null
    : level === 'HLD' && parentId && !['actor', 'deployment', 'system', 'integration'].includes(selected.type) ? { type: 'component', id: parentId }
      : selected
  const marked = useMemo(() => {
    const keys = new Set()
    if (level === 'LLD' && selected?.type === 'component') (index.modulesByComponent[selected.id] || []).forEach((m) => keys.add(`module:${m.module_id}`))
    if (level === 'LLD' && selected?.type === 'module' && parentId) keys.add(`component:${parentId}`)
    return keys
  }, [level, selected, parentId, index])

  const detail = describeRef(selected, hld, lld)
  const actions = []
  if (detail && parentId) {
    const hasLld = (index.modulesByComponent[parentId] || []).length || (index.apisByComponent[parentId] || []).length
    if (level === 'HLD' && hasLld) actions.push({ label: 'Open in LLD', go: { level: 'LLD', componentId: parentId, ref: selected } })
    if (level === 'LLD') actions.push({ label: 'Show in HLD', go: { level: 'HLD', componentId: parentId, ref: selected } })
  }

  const go = ({ level: target, componentId, ref }) => {
    setLevel(target)
    if (target === 'LLD') {
      const hasModules = (index.modulesByComponent[componentId] || []).length > 0
      setLldView(hasModules ? 'class' : 'api')
      setFocus(componentId)
    } else {
      setHldView('architecture')
    }
    setSelected(ref || { type: 'component', id: componentId })
  }
  const pick = (ref) => setSelected(ref)

  const isSequence = view === 'sequence'
  const flows = level === 'HLD' ? hldFlows : lldFlows
  const activeFlow = level === 'HLD' ? (hldFlow || hldFlows[0]?.flow_id) : (lldFlow || lldFlows[0]?.sequence_id)
  const resetKey = `${level}-${view}-${focusId}-${activeFlow}`
  const label = `${level} ${(level === 'HLD' ? HLD_VIEWS : LLD_VIEWS).find((v) => v.key === view)?.label} diagram`
  const counts = isSequence ? `${model.participants?.length || 0} participants · ${model.messages?.length || 0} messages` : `${model.nodes?.length || 0} elements · ${model.edges?.length || 0} connections`

  return (
    <section className="space-y-4" aria-label="Visual architecture diagrams">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold text-text-primary">Architecture diagrams</h3>
          <p className="text-sm text-text-secondary" data-testid="level-blurb">{BLURB[level]}</p>
        </div>
        <div className="inline-flex rounded-lg border border-border-light overflow-hidden" role="group" aria-label="Design level">
          {['HLD', 'LLD'].map((key) => (
            <button key={key} onClick={() => setLevel(key)} aria-pressed={level === key} className={`px-5 py-2 text-sm font-semibold transition-colors ${level === key ? 'bg-primary text-white' : 'bg-white text-text-secondary hover:bg-bg-light'}`}>{key}</button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label={`${level} diagrams`}>
        {(level === 'HLD' ? HLD_VIEWS : LLD_VIEWS).map((item) => (
          <button key={item.key} role="tab" aria-selected={view === item.key} onClick={() => (level === 'HLD' ? setHldView(item.key) : setLldView(item.key))} className={chip(view === item.key)}>{item.label}</button>
        ))}
      </div>

      {(focusOptions.length > 0 || (isSequence && flows.length > 1) || (view === 'dataflow' && hldFlows.length > 1)) && (
        <div className="flex flex-wrap items-center gap-2" data-testid="diagram-selector">
          <span className="text-xs font-medium text-text-secondary">{focusOptions.length ? 'Component:' : 'Flow:'}</span>
          {focusOptions.length > 0 && focusOptions.map((c) => (
            <button key={c.component_id} onClick={() => { setFocus(c.component_id); setSelected({ type: 'component', id: c.component_id }) }} className={subChip(focusId === c.component_id)}>{c.component_id} {c.name}</button>
          ))}
          {!focusOptions.length && (level === 'HLD' ? hldFlows : lldFlows).map((flow) => {
            const id = flow.flow_id || flow.sequence_id
            return <button key={id} onClick={() => (level === 'HLD' ? setHldFlow(id) : setLldFlow(id))} className={subChip(activeFlow === id)}>{id} {flow.name}</button>
          })}
        </div>
      )}

      <p className="text-xs text-text-secondary">{VIEW_HELP[`${level}:${view}`]}</p>
      {model.notes?.length > 0 && (
        <div className="text-xs text-text-secondary bg-bg-light border border-border-light rounded-lg px-3 py-2 space-y-0.5" data-testid="diagram-notes">{model.notes.map((n) => <p key={n}>{n}</p>)}</div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px] items-start">
        <div className="min-w-0 space-y-2">
          {model.empty ? <Empty model={model} /> : isSequence ? (
            <SequenceDiagram model={model} selected={canvasSelected} highlightIds={marked} onSelect={pick} label={label} resetKey={resetKey} />
          ) : (
            <GraphDiagram model={model} selected={canvasSelected} highlightIds={marked} onSelect={pick} label={label} resetKey={resetKey} />
          )}
          {!model.empty && (
            <p className="text-xs text-text-secondary flex flex-wrap items-center gap-x-4 gap-y-1">
              <span data-testid="diagram-counts">{counts}</span>
              <span className="flex items-center gap-1.5"><span className="w-5 border-t-2 border-dashed border-gray-400" /> dashed outline = assumed / inferred</span>
              <span>Click to select · hover to highlight connections</span>
            </p>
          )}
        </div>
        <DetailPanel detail={detail} actions={actions} onPick={pick} onGo={go} />
      </div>
    </section>
  )
}

export default VisualArchitecture
