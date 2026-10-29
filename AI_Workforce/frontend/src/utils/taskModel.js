export const STATUS_ORDER = ['TODO', 'IN_PROGRESS', 'COMPLETED']
export const PRIORITY_ORDER = ['HIGH', 'MEDIUM', 'LOW']

export function flattenTasks(projects, plans) {
  const rows = []
  projects.forEach((project, index) => {
    const plan = plans[index]
    const tasks = Array.isArray(plan?.tasks) ? plan.tasks : []
    const sprints = Array.isArray(plan?.sprints) ? plan.sprints : []
    const sprintById = Object.fromEntries(sprints.map((sprint) => [sprint.sprint_id, sprint]))
    tasks.forEach((task) => {
      const sprint = sprintById[task.sprint]
      rows.push({
        key: `${project.id}-${task.id ?? task.task_id}`,
        taskId: task.task_id || String(task.id ?? ''),
        title: task.title || 'Untitled task',
        description: task.description || '',
        projectId: project.id,
        project: project.name,
        role: task.suggested_role || '',
        priority: task.priority || '',
        points: Number.isFinite(Number(task.story_points)) ? Number(task.story_points) : null,
        status: task.status || '',
        sprint: sprint?.name || task.sprint || '',
        sprintEnd: sprint?.end_date || null,
      })
    })
  })
  return rows
}

export function filterTasks(rows, { search = '', project = 'all', status = 'all', priority = 'all' } = {}) {
  const term = search.trim().toLowerCase()
  return rows.filter((row) => {
    if (project !== 'all' && String(row.projectId) !== String(project)) return false
    if (status !== 'all' && row.status !== status) return false
    if (priority !== 'all' && row.priority !== priority) return false
    if (!term) return true
    return [row.title, row.taskId, row.project, row.role, row.sprint].some((value) => String(value).toLowerCase().includes(term))
  })
}

export function paginate(rows, page, size) {
  const pages = Math.max(1, Math.ceil(rows.length / size))
  const current = Math.min(Math.max(1, page), pages)
  const start = (current - 1) * size
  return { items: rows.slice(start, start + size), page: current, pages, start: rows.length ? start + 1 : 0, end: Math.min(start + size, rows.length) }
}

export function countBy(rows, field) {
  return rows.reduce((acc, row) => {
    acc[row[field]] = (acc[row[field]] || 0) + 1
    return acc
  }, {})
}
