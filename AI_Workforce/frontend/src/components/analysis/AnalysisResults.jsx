import { useState } from 'react'

const TABS = [
  { key: 'functional_requirements', label: 'Functional' },
  { key: 'non_functional_requirements', label: 'Non-Functional' },
  { key: 'user_stories', label: 'User Stories' },
  { key: 'acceptance_criteria', label: 'Acceptance Criteria' },
  { key: 'dependencies', label: 'Dependencies' },
  { key: 'ambiguities', label: 'Ambiguities' },
  { key: 'constraints', label: 'Constraints' },
  { key: 'risks', label: 'Risks' },
]

const LEVEL_STYLES = {
  HIGH: 'badge-danger',
  MEDIUM: 'badge-warning',
  LOW: 'badge-success',
}

function Level({ value, prefix }) {
  if (!value) return null
  return <span className={`badge ${LEVEL_STYLES[value] || 'bg-gray-100 text-text-secondary'}`}>{prefix ? `${prefix}: ` : ''}{value}</span>
}

function Sources({ refs }) {
  if (!refs?.length) return null
  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {refs.map((ref, index) => (
        <span key={index} className="text-xs bg-bg-light text-text-secondary px-2 py-1 rounded" title={ref.source}>
          {ref.document} · p.{ref.page}
        </span>
      ))}
    </div>
  )
}

function Item({ title, body, badges, meta, refs }) {
  return (
    <div className="border border-border-light rounded-lg p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {title && <p className="font-semibold text-text-primary mb-1">{title}</p>}
          <p className="text-sm text-text-secondary whitespace-pre-wrap">{body}</p>
          {meta && <p className="text-xs text-text-secondary mt-2">{meta}</p>}
        </div>
        <div className="flex flex-col gap-1 items-end shrink-0">{badges}</div>
      </div>
      <Sources refs={refs} />
    </div>
  )
}

function renderItem(key, item, storyTitleById) {
  switch (key) {
    case 'functional_requirements':
      return <Item key={item.id} title={item.title} body={item.description} refs={item.source_references}
        meta={item.priority_basis && item.priority_basis !== 'UNSPECIFIED' ? `Priority ${item.priority_basis.toLowerCase()}` : null}
        badges={<Level value={item.priority} />} />
    case 'non_functional_requirements':
      return <Item key={item.id} title={item.category} body={item.description} refs={item.source_references}
        badges={<Level value={item.priority} />} />
    case 'user_stories':
      return <Item key={item.id} title={item.title} body={item.story} refs={item.source_references}
        badges={<Level value={item.priority} />} />
    case 'acceptance_criteria':
      return <Item key={item.id} title={storyTitleById[item.user_story_id] || null} body={item.description} refs={item.source_references} />
    case 'dependencies':
      return <Item key={item.id} body={item.description} refs={item.source_references}
        meta={item.related_requirement && `Related: ${item.related_requirement}`} />
    case 'ambiguities':
      return <Item key={item.id} body={item.description} refs={item.source_references}
        meta={item.related_requirement && `Related: ${item.related_requirement}`}
        badges={<Level value={item.impact} prefix="Impact" />} />
    case 'constraints':
      return <Item key={item.id} body={item.description} refs={item.source_references} />
    case 'risks':
      return <Item key={item.id} body={item.description} refs={item.source_references}
        meta={item.related_requirement && `Related: ${item.related_requirement}`}
        badges={<Level value={item.severity} prefix="Severity" />} />
    default:
      return null
  }
}

function AnalysisResults({ analysis }) {
  const [active, setActive] = useState(TABS[0].key)
  if (!analysis || analysis.latest_agent_run?.status !== 'COMPLETED') {
    return (
      <p className="text-sm text-text-secondary">
        No completed analysis yet. Upload an SRS and run the Requirements Analyst from the AI Agents page.
      </p>
    )
  }

  const summary = analysis.project_summary || {}
  const storyTitleById = Object.fromEntries((analysis.user_stories || []).map((s) => [s.id, s.title]))
  const items = analysis[active] || []
  const completedAt = analysis.latest_agent_run.completed_at

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-text-primary">Project Summary</h3>
          {completedAt && <span className="text-xs text-text-secondary">Analyzed {new Date(completedAt).toLocaleString()}</span>}
        </div>
        <p className="text-sm text-text-secondary">{summary.summary}</p>
        {summary.scope && <p className="text-sm text-text-secondary mt-2"><span className="font-medium text-text-primary">Scope: </span>{summary.scope}</p>}
        {!!summary.actors?.length && (
          <div className="flex flex-wrap gap-2 mt-3">
            {summary.actors.map((actor) => <span key={actor} className="badge bg-purple-100 text-primary">{actor}</span>)}
          </div>
        )}
      </div>

      <div>
        <div className="flex flex-wrap gap-2 mb-4">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActive(tab.key)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                active === tab.key ? 'bg-primary text-white' : 'bg-bg-light text-text-secondary hover:text-text-primary'
              }`}
            >
              {tab.label} ({(analysis[tab.key] || []).length})
            </button>
          ))}
        </div>
        <div className="space-y-3">
          {!items.length && <p className="text-sm text-text-secondary">Nothing was identified in this category.</p>}
          {items.map((item) => renderItem(active, item, storyTitleById))}
        </div>
      </div>
    </div>
  )
}

export default AnalysisResults
