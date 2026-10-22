import { useState } from 'react'
import { AlertTriangle, Lock } from 'lucide-react'

const LEVEL = { HIGH: 'badge-danger', MEDIUM: 'badge-warning', LOW: 'badge-success' }
const GROUNDING = {
  EXPLICIT: 'badge-success',
  INFERRED: 'badge-info',
  AMBIGUOUS: 'badge-warning',
  UNKNOWN: 'bg-gray-100 text-text-secondary',
}

function Badge({ children, className = 'bg-gray-100 text-text-secondary', title }) {
  return <span className={`badge ${className}`} title={title}>{children}</span>
}

function Chip({ children }) {
  return <span className="text-xs bg-bg-light text-text-secondary px-2 py-1 rounded">{children}</span>
}

function Sources({ refs }) {
  if (!refs?.length) return null
  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {refs.map((ref, index) => <Chip key={index}>{ref.document} · p.{ref.page}</Chip>)}
    </div>
  )
}

function Metric({ label, value }) {
  return (
    <div className="bg-bg-light rounded-lg p-4">
      <p className="text-2xl font-bold text-primary">{value}</p>
      <p className="text-xs text-text-secondary mt-1">{label}</p>
    </div>
  )
}

function Empty({ children }) {
  return <p className="text-sm text-text-secondary">{children}</p>
}

function Overview({ plan, taskById }) {
  const info = plan.plan
  const points = plan.tasks.reduce((sum, task) => sum + task.story_points, 0)
  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-semibold text-text-primary mb-2">Execution Summary</h3>
        <p className="text-sm text-text-secondary">{info.execution_summary}</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Metric label="Tasks" value={plan.tasks.length} />
        <Metric label="Story points" value={points} />
        <Metric label="Sprints" value={plan.sprints.length} />
        <Metric label="Milestones" value={plan.milestones.length} />
        <Metric label="Risks" value={plan.risks.length} />
      </div>

      {!!plan.epics.length && (
        <div>
          <h3 className="font-semibold text-text-primary mb-3">Epics</h3>
          <div className="space-y-3">
            {plan.epics.map((epic) => (
              <div key={epic.id} className="border border-border-light rounded-lg p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-text-primary">{epic.title}</p>
                    <p className="text-sm text-text-secondary mt-1">{epic.description}</p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    {epic.priority && <Badge className={LEVEL[epic.priority]}>{epic.priority}</Badge>}
                    <Badge>{epic.task_ids.length} tasks</Badge>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h3 className="font-semibold text-text-primary mb-3">Definition of Done</h3>
        <ul className="space-y-2">
          {info.definition_of_done.map((item, index) => (
            <li key={index} className="flex items-start gap-2 text-sm text-text-secondary">
              <span className="mt-0.5 text-primary">✓</span>{item}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3 className="font-semibold text-text-primary mb-3">Execution Order</h3>
        <p className="text-xs text-text-secondary mb-2">Dependencies always come before the tasks that need them.</p>
        <div className="flex flex-wrap gap-2">
          {info.execution_order.map((taskId, index) => (
            <span key={taskId} className="text-xs bg-purple-100 text-primary px-2 py-1 rounded" title={taskById[taskId]?.title}>
              {index + 1}. {taskId}
            </span>
          ))}
        </div>
      </div>

      {!!info.assumptions.length && (
        <div>
          <h3 className="font-semibold text-text-primary mb-2">Assumptions</h3>
          <ul className="list-disc pl-5 text-sm text-text-secondary space-y-1">
            {info.assumptions.map((item, index) => <li key={index}>{item}</li>)}
          </ul>
        </div>
      )}

      {!!info.warnings.length && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <p className="text-sm font-medium text-yellow-800 mb-2">Notes from validation</p>
          <ul className="list-disc pl-5 text-sm text-yellow-800 space-y-1">
            {info.warnings.map((item, index) => <li key={index}>{item}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

function Tasks({ plan }) {
  const [sprint, setSprint] = useState('ALL')
  const tasks = plan.tasks.filter((task) => sprint === 'ALL' || task.sprint === sprint)
  return (
    <div>
      <label className="text-sm text-text-secondary">Sprint
        <select value={sprint} onChange={(e) => setSprint(e.target.value)} className="input-field ml-3">
          <option value="ALL">All sprints</option>
          {plan.sprints.map((s) => <option key={s.sprint_id} value={s.sprint_id}>{s.name}</option>)}
        </select>
      </label>
      <div className="space-y-3 mt-4">
        {!tasks.length && <Empty>No tasks in this sprint.</Empty>}
        {tasks.map((task) => (
          <div key={task.id} className="border border-border-light rounded-lg p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-text-primary"><span className="text-text-secondary font-normal">{task.task_id}</span> {task.title}</p>
                <p className="text-sm text-text-secondary mt-1 whitespace-pre-wrap">{task.description}</p>
              </div>
              <div className="flex flex-col gap-1 items-end shrink-0">
                <Badge className={LEVEL[task.priority]}>{task.priority}</Badge>
                <Badge className="bg-purple-100 text-primary">{task.story_points} pts</Badge>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              <Badge className="badge-info">{task.suggested_role}</Badge>
              <Badge className={GROUNDING[task.grounding]} title="How well the requirements support this task">{task.grounding}</Badge>
              <Chip>{plan.sprints.find((s) => s.sprint_id === task.sprint)?.name || task.sprint}</Chip>
              <Chip>{task.status}</Chip>
            </div>
            {!!task.dependencies.length && (
              <p className="text-xs text-text-secondary mt-3">Depends on: {task.dependencies.join(', ')}</p>
            )}
            {(task.related_requirement_title || task.related_story_title) && (
              <p className="text-xs text-text-secondary mt-1">
                {task.related_requirement_title && <>Requirement: {task.related_requirement_title}</>}
                {task.related_requirement_title && task.related_story_title && ' · '}
                {task.related_story_title && <>Story: {task.related_story_title}</>}
              </p>
            )}
            {task.rationale && <p className="text-xs text-text-secondary mt-1 italic">Why: {task.rationale}</p>}
            {!!task.acceptance_criteria.length && (
              <ul className="list-disc pl-5 text-sm text-text-secondary mt-3 space-y-1">
                {task.acceptance_criteria.map((item, index) => <li key={index}>{item}</li>)}
              </ul>
            )}
            <Sources refs={task.source_references} />
          </div>
        ))}
      </div>
    </div>
  )
}

function Sprints({ plan, taskById }) {
  if (!plan.sprints.length) return <Empty>No sprints were planned.</Empty>
  return (
    <div className="space-y-3">
      {plan.sprints.map((sprint) => (
        <div key={sprint.id} className="border border-border-light rounded-lg p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-text-primary">{sprint.name}</p>
              <p className="text-sm text-text-secondary mt-1">{sprint.goal}</p>
            </div>
            <div className="flex gap-2 shrink-0">
              <Badge>{sprint.tasks.length} tasks</Badge>
              <Badge className="bg-purple-100 text-primary">{sprint.total_story_points} pts</Badge>
            </div>
          </div>
          <p className="text-xs text-text-secondary mt-2">
            {sprint.start_date && sprint.end_date ? `${sprint.start_date} → ${sprint.end_date}` : 'Dates not set (project start date or team capacity not provided)'}
          </p>
          {sprint.capacity_notes && <p className="text-xs text-text-secondary mt-1">Capacity: {sprint.capacity_notes}</p>}
          <ul className="mt-3 space-y-1">
            {sprint.tasks.map((taskId) => (
              <li key={taskId} className="text-sm text-text-secondary">
                <span className="font-medium text-text-primary">{taskId}</span> {taskById[taskId]?.title}
                <span className="text-xs"> · {taskById[taskId]?.story_points} pts</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

function Dependencies({ plan, taskById }) {
  if (!plan.dependencies.length) return <Empty>No dependencies were identified.</Empty>
  const label = (id) => (id ? `${id} ${taskById[id]?.title || ''}` : null)
  return (
    <div className="space-y-3">
      {!!plan.blocking_dependencies.length && (
        <div className="flex items-center gap-2 text-sm text-yellow-800 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
          <Lock className="w-4 h-4" /> {plan.blocking_dependencies.length} blocking dependencies must be resolved before the dependent tasks can start.
        </div>
      )}
      {plan.dependencies.map((dep) => (
        <div key={dep.id} className="border border-border-light rounded-lg p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="text-sm">
              <p className="text-text-primary font-medium">{label(dep.task_id)}</p>
              <p className="text-text-secondary mt-1">
                {dep.depends_on_task_id ? <>waits for <span className="font-medium text-text-primary">{label(dep.depends_on_task_id)}</span></> : 'waits for an external dependency'}
              </p>
              <p className="text-text-secondary mt-1">{dep.description}</p>
            </div>
            <div className="flex flex-col gap-1 items-end shrink-0">
              <Badge className="badge-info">{dep.dependency_type}</Badge>
              {dep.is_blocking && <Badge className="badge-danger">BLOCKING</Badge>}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function Milestones({ plan, taskById }) {
  if (!plan.milestones.length) return <Empty>No milestones were defined.</Empty>
  return (
    <div className="space-y-3">
      {plan.milestones.map((milestone) => (
        <div key={milestone.id} className="border border-border-light rounded-lg p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-text-primary">{milestone.title}</p>
              <p className="text-sm text-text-secondary mt-1">{milestone.description}</p>
            </div>
            {milestone.target_sprint_id && (
              <Badge>{plan.sprints.find((s) => s.sprint_id === milestone.target_sprint_id)?.name || milestone.target_sprint_id}</Badge>
            )}
          </div>
          <ul className="mt-3 space-y-1">
            {milestone.task_ids.map((taskId) => (
              <li key={taskId} className="text-sm text-text-secondary">
                <span className="font-medium text-text-primary">{taskId}</span> {taskById[taskId]?.title}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

function Risks({ plan }) {
  if (!plan.risks.length) return <Empty>No risks were identified.</Empty>
  return (
    <div className="space-y-3">
      {plan.risks.map((risk) => (
        <div key={risk.id} className="border border-border-light rounded-lg p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-text-primary">{risk.title}</p>
              <p className="text-sm text-text-secondary mt-1">{risk.description}</p>
            </div>
            <div className="flex flex-col gap-1 items-end shrink-0">
              <Badge className={LEVEL[risk.impact]}>Impact: {risk.impact}</Badge>
              <Badge className={LEVEL[risk.likelihood]}>Likelihood: {risk.likelihood}</Badge>
            </div>
          </div>
          <p className="text-sm text-text-secondary mt-3"><span className="font-medium text-text-primary">Mitigation: </span>{risk.mitigation}</p>
          {!!risk.related_tasks.length && <p className="text-xs text-text-secondary mt-2">Related tasks: {risk.related_tasks.join(', ')}</p>}
        </div>
      ))}
    </div>
  )
}

function PlanResults({ plan }) {
  const [active, setActive] = useState('overview')
  if (!plan?.plan) {
    return (
      <div className="text-sm text-text-secondary">
        {plan?.status === 'FAILED' && plan.latest_agent_run?.error
          ? `The last attempt to generate a plan failed: ${plan.latest_agent_run.error}`
          : 'No project plan yet. Run the Requirements Analyst, then the Project Manager from the AI Agents page.'}
      </div>
    )
  }

  const taskById = Object.fromEntries(plan.tasks.map((task) => [task.task_id, task]))
  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'tasks', label: `Tasks (${plan.tasks.length})` },
    { key: 'sprints', label: `Sprints (${plan.sprints.length})` },
    { key: 'dependencies', label: `Dependencies (${plan.dependencies.length})` },
    { key: 'milestones', label: `Milestones (${plan.milestones.length})` },
    { key: 'risks', label: `Risks (${plan.risks.length})` },
  ]

  return (
    <div className="space-y-4">
      {plan.plan.requirements_changed && (
        <div className="flex items-start gap-2 text-sm text-yellow-800 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          The requirements were re-analyzed after this plan was generated. Regenerate the plan to keep it in sync.
        </div>
      )}
      {plan.status === 'FAILED' && plan.latest_agent_run?.error && (
        <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          The latest regeneration failed, so the previous plan is shown. {plan.latest_agent_run.error}
        </div>
      )}
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActive(tab.key)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                active === tab.key ? 'bg-primary text-white' : 'bg-bg-light text-text-secondary hover:text-text-primary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {plan.plan.created_at && (
          <span className="text-xs text-text-secondary whitespace-nowrap ml-3">Generated {new Date(plan.plan.created_at).toLocaleString()}</span>
        )}
      </div>
      {active === 'overview' && <Overview plan={plan} taskById={taskById} />}
      {active === 'tasks' && <Tasks plan={plan} />}
      {active === 'sprints' && <Sprints plan={plan} taskById={taskById} />}
      {active === 'dependencies' && <Dependencies plan={plan} taskById={taskById} />}
      {active === 'milestones' && <Milestones plan={plan} taskById={taskById} />}
      {active === 'risks' && <Risks plan={plan} />}
    </div>
  )
}

export default PlanResults
