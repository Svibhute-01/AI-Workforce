import { pct } from './format.js'

export const STATUS_META = {
  TODO: { label: 'To do', color: '#E9C65E' },
  IN_PROGRESS: { label: 'In progress', color: '#7BA7D1' },
  COMPLETED: { label: 'Completed', color: '#7FB069' },
}

export const statusColor = (key) => STATUS_META[key]?.color || '#B9A877'

export function buildReport(summary) {
  if (!summary) return null
  const projects = summary.projects || {}
  const tasks = summary.tasks || {}
  const agents = Array.isArray(summary.agents) ? summary.agents : []
  const overview = Array.isArray(summary.project_overview) ? summary.project_overview : []

  const statusRows = (Array.isArray(tasks.by_status) ? tasks.by_status : []).map((row) => ({
    key: row.key,
    label: STATUS_META[row.key]?.label || row.label || row.key,
    count: row.count || 0,
    share: pct(row.count || 0, tasks.total || 0),
    color: statusColor(row.key),
  }))

  const agentRuns = agents.reduce((sum, agent) => sum + (agent.total_runs || 0), 0)
  const agentFailed = agents.reduce((sum, agent) => sum + (agent.failed || 0), 0)

  const projectRows = overview.map((project) => ({
    id: project.id,
    name: project.name,
    status: project.status,
    progress: project.progress,
    tasksTotal: project.tasks_total || 0,
    tasksCompleted: project.tasks_completed || 0,
    overdueTasks: project.overdue_tasks || 0,
    documents: project.documents || 0,
    dueDate: project.due_date || null,
    overdue: Boolean(project.is_overdue),
  }))

  return {
    generatedAt: summary.generated_at || null,
    totals: {
      projects: projects.total || 0,
      newProjects: projects.new_last_7_days || 0,
      overdueProjects: projects.overdue || 0,
      tasks: tasks.total || 0,
      completed: tasks.completed || 0,
      completionRate: tasks.completion_rate ?? null,
      overdueTasks: tasks.overdue || 0,
      storyPoints: tasks.total_story_points || 0,
      completedStoryPoints: tasks.completed_story_points || 0,
      agentRuns,
      agentFailed,
    },
    statusRows,
    priorityRows: Array.isArray(tasks.by_priority) ? tasks.by_priority : [],
    roleRows: Array.isArray(tasks.by_role) ? tasks.by_role : [],
    projectRows,
    agents,
    pipeline: Array.isArray(summary.insights?.pipeline) ? summary.insights.pipeline : [],
    recentRuns: Array.isArray(summary.recent_agent_runs) ? summary.recent_agent_runs : [],
  }
}

const csvCell = (value) => {
  const text = value == null ? '' : String(value)
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function reportToCsv(report) {
  const lines = [
    ['Project', 'Status', 'Progress %', 'Tasks completed', 'Tasks total', 'Overdue tasks', 'Documents', 'Due date'],
    ...report.projectRows.map((row) => [
      row.name, row.status, row.progress ?? '', row.tasksCompleted, row.tasksTotal, row.overdueTasks, row.documents, row.dueDate ?? '',
    ]),
  ]
  return lines.map((line) => line.map(csvCell).join(',')).join('\n')
}
