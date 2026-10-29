const runTime = (run) => run.completed_at || run.started_at || run.created_at || null

const describeRun = (run) => {
  if (run.error) return run.error
  const out = run.output_summary || {}
  const parts = [run.status ? String(run.status).toLowerCase() : 'recorded']
  if (out.requirements_generated) parts.push(`${out.requirements_generated} requirements generated`)
  if (out.tasks_generated) parts.push(`${out.tasks_generated} tasks planned`)
  if (out.components) parts.push(`${out.components} components, ${out.apis ?? 0} APIs designed`)
  return parts.join(' · ')
}

export function buildActivity(project, documents, runs) {
  const events = []
  if (project?.created_at) {
    events.push({ id: `project-${project.id}`, kind: 'project', title: 'Project created', detail: project.name, at: project.created_at })
  }
  ;(Array.isArray(documents) ? documents : []).forEach((doc) => {
    if (!doc.upload_time) return
    events.push({ id: `doc-${doc.id}`, kind: 'document', title: `Document uploaded: ${doc.filename}`, detail: doc.processing_status ? `Processing ${String(doc.processing_status).toLowerCase()}` : '', at: doc.upload_time })
  })
  ;(Array.isArray(runs) ? runs : []).forEach((run) => {
    const at = runTime(run)
    if (!at) return
    events.push({ id: `run-${run.id}`, kind: 'run', status: run.status, title: run.agent_name || 'Agent run', detail: describeRun(run), at })
  })
  return events.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
}

export function latestRunByAgent(runs) {
  const latest = {}
  ;(Array.isArray(runs) ? runs : []).forEach((run) => {
    const key = run.agent_name
    if (!key) return
    const time = new Date(runTime(run) || 0).getTime()
    if (!latest[key] || time > new Date(runTime(latest[key]) || 0).getTime()) latest[key] = run
  })
  return latest
}
