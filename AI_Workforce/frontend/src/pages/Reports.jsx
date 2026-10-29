import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, AlertTriangle, BarChart3, Bot, CheckCircle, Clock, Download, Folder, Info, Layers, ListChecks, RefreshCw, Target } from 'lucide-react'
import StatCard from '../components/common/StatCard'
import ProgressBar from '../components/common/ProgressBar'
import { EmptyState, ErrorState, Notice, PageHeader, Skeleton } from '../components/common/States'
import apiService from '../services/api'
import { fmtDate, fmtDuration, timeAgo } from '../utils/format'
import { buildReport, reportToCsv } from '../utils/reportModel'

function Panel({ title, icon: Icon, action, children, className = '' }) {
  return (
    <section className={`card p-6 ${className}`}>
      <div className="mb-5 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-base font-extrabold text-text-primary">
          {Icon && <Icon className="h-4 w-4 text-primary" />}
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function Donut({ rows, total }) {
  const radius = 62
  const circumference = 2 * Math.PI * radius
  let offset = 0
  return (
    <svg viewBox="0 0 170 170" className="h-44 w-44 shrink-0" role="img" aria-label={`${total} tasks by status`}>
      <g transform="rotate(-90 85 85)">
        <circle cx="85" cy="85" r={radius} fill="none" stroke="#E9C65E" strokeOpacity="0.35" strokeWidth="20" />
        {rows.filter((row) => row.count > 0).map((row) => {
          const length = (row.count / total) * circumference
          const arc = (
            <circle
              key={row.key}
              cx="85" cy="85" r={radius} fill="none" strokeWidth="20" strokeLinecap="butt"
              stroke={row.color}
              strokeDasharray={`${length} ${circumference - length}`}
              strokeDashoffset={-offset}
              style={{ transition: 'stroke-dasharray 0.8s ease' }}
            >
              <title>{`${row.label}: ${row.count} (${row.share}%)`}</title>
            </circle>
          )
          offset += length
          return arc
        })}
      </g>
      <text x="85" y="84" textAnchor="middle" fontSize="30" fontWeight="800" fill="#34312B">{total}</text>
      <text x="85" y="104" textAnchor="middle" fontSize="11" fontWeight="600" fill="#696042">Total tasks</text>
    </svg>
  )
}

function ReportSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading report">
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-32" />)}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-80" />
        <Skeleton className="h-80" />
      </div>
      <Skeleton className="h-64" />
    </div>
  )
}

function Reports() {
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const alive = useRef(true)

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    try {
      const summary = await apiService.dashboard.getSummary()
      if (!alive.current) return
      setReport(buildReport(summary))
      setError('')
    } catch (requestError) {
      if (alive.current) setError(requestError.message || 'Could not load the report.')
    } finally {
      if (alive.current) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  useEffect(() => {
    alive.current = true
    load()
    return () => { alive.current = false }
  }, [load])

  const exportCsv = () => {
    const blob = new Blob([reportToCsv(report)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `ai-workforce-project-report-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  const totals = report?.totals
  const hasProjects = totals && totals.projects > 0

  return (
    <div>
      <PageHeader
        title="Reports & Analytics"
        subtitle="Live insights computed from your projects, plans and agent runs"
        actions={(
          <>
            {report && (
              <span className="hidden items-center gap-1.5 text-xs text-text-secondary sm:flex">
                <Clock className="h-3.5 w-3.5" /> Updated {timeAgo(report.generatedAt)}
              </span>
            )}
            <button type="button" onClick={exportCsv} disabled={!hasProjects} className="btn-secondary flex items-center gap-2">
              <Download className="h-4 w-4" /> Export CSV
            </button>
            <button type="button" onClick={() => load(true)} disabled={loading || refreshing} className="btn-outline flex items-center gap-2">
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
            </button>
          </>
        )}
      />

      {loading && !report ? (
        <ReportSkeleton />
      ) : !report ? (
        <ErrorState title="Couldn't load your report" message={error} onRetry={() => load()} retrying={loading} />
      ) : !hasProjects ? (
        <EmptyState icon={BarChart3} title="No data to report yet" hint="Create a project, upload an SRS and run the AI agents. Analytics appear here as soon as work exists." to="/projects" cta="Create a project" />
      ) : (
        <div className="space-y-6">
          {error && <Notice tone="error" onRetry={() => load(true)}>Refresh failed: {error}. Showing the last loaded data.</Notice>}

          <div className="bt-stagger grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard title="Total projects" value={totals.projects} icon={Folder}
              change={totals.newProjects ? `${totals.newProjects} new in the last 7 days` : 'None created in the last 7 days'} />
            <StatCard title="Tasks completed" value={totals.completed} icon={CheckCircle}
              change={totals.tasks ? `of ${totals.tasks} planned tasks` : 'No tasks planned yet'} />
            <StatCard title="Completion rate" value={totals.completionRate == null ? '—' : `${totals.completionRate}%`} icon={Target}
              change={totals.completionRate == null ? 'Needs a generated plan' : `${totals.completedStoryPoints}/${totals.storyPoints} story points done`} />
            <StatCard title="Agent runs" value={totals.agentRuns} icon={Bot}
              change={totals.agentRuns ? `${totals.agentFailed} failed` : 'No runs recorded yet'}
              trend={totals.agentFailed > 0 ? 'down' : 'none'} />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Panel title="Task status distribution" icon={ListChecks}>
              {totals.tasks === 0 ? (
                <EmptyState icon={ListChecks} title="No tasks yet" hint="Tasks appear once the Project Manager AI generates a plan." to="/agents" cta="Open AI Agents" />
              ) : (
                <div className="flex flex-col items-center gap-6 sm:flex-row">
                  <Donut rows={report.statusRows} total={totals.tasks} />
                  <ul className="w-full space-y-3 text-sm">
                    {report.statusRows.map((row) => (
                      <li key={row.key} className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2 text-text-secondary">
                          <span className="h-3 w-3 rounded-full border border-brand-ink/40" style={{ background: row.color }} />{row.label}
                        </span>
                        <span className="font-bold text-text-primary">{row.count} <span className="font-medium text-text-secondary">({row.share}%)</span></span>
                      </li>
                    ))}
                    {report.priorityRows.length > 0 && (
                      <li className="border-t border-border-light pt-3">
                        <p className="mb-2 text-xs font-bold uppercase tracking-wide text-text-secondary">By priority</p>
                        <div className="flex flex-wrap gap-2">
                          {report.priorityRows.map((row) => <span key={row.key} className="bt-chip">{row.label}: {row.count}</span>)}
                        </div>
                      </li>
                    )}
                  </ul>
                </div>
              )}
            </Panel>

            <Panel title="Project progress overview" icon={Layers} action={<Link to="/projects" className="text-sm font-bold text-primary hover:underline">All projects</Link>}>
              <div className="space-y-5">
                {report.projectRows.slice(0, 8).map((project) => (
                  <Link key={project.id} to={`/projects/${project.id}`} className="group -m-2 block rounded-xl p-2 transition-colors hover:bg-brand-soft/40">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-bold text-text-primary">{project.name}</p>
                      <span className="shrink-0 text-xs text-text-secondary">
                        {project.progress == null ? 'No plan yet' : `${project.tasksCompleted}/${project.tasksTotal} tasks`}
                      </span>
                    </div>
                    <ProgressBar progress={project.progress ?? 0} tone={project.overdueTasks ? 'alert' : 'butter'} size="md" />
                  </Link>
                ))}
              </div>
            </Panel>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Panel title="Agent performance" icon={Activity}>
              {report.agents.length === 0 ? (
                <EmptyState icon={Bot} title="No agent data" hint="Agent statistics appear after the first run." />
              ) : (
                <div className="space-y-4">
                  {report.agents.map((agent) => (
                    <div key={agent.key} className="rounded-xl border border-border-light bg-brand-lemon/50 p-4">
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-extrabold text-text-primary">{agent.name}</p>
                          <p className="text-xs text-text-secondary">{agent.stage}</p>
                        </div>
                        <span className="text-xs text-text-secondary">{agent.total_runs ? `Last run ${timeAgo(agent.last_run_at)}` : 'No runs yet'}</span>
                      </div>
                      {agent.total_runs > 0 && (
                        <>
                          <ProgressBar progress={agent.success_rate ?? 0} tone="leaf" size="sm" showLabel={false} />
                          <p className="mt-2 text-xs text-text-secondary">
                            {agent.total_runs} run{agent.total_runs === 1 ? '' : 's'} · {agent.success_rate == null ? 'success rate n/a' : `${agent.success_rate}% success`} · avg {fmtDuration(agent.avg_duration_seconds)}
                            {agent.failed > 0 && <span className="text-red-700"> · {agent.failed} failed</span>}
                          </p>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="SDLC pipeline" icon={Layers}>
              {report.pipeline.length === 0 ? (
                <EmptyState icon={Layers} title="No pipeline data yet" />
              ) : (
                <div className="space-y-4">
                  {report.pipeline.map((stage) => {
                    const max = Math.max(...report.pipeline.map((s) => s.count), 1)
                    return (
                      <div key={stage.key}>
                        <div className="mb-1.5 flex items-center justify-between text-sm">
                          <span className="font-semibold text-text-primary">{stage.label}</span>
                          <span className="text-xs text-text-secondary">{stage.count} of {totals.projects} project{totals.projects === 1 ? '' : 's'}</span>
                        </div>
                        <ProgressBar progress={(stage.count / max) * 100} showLabel={false} size="sm" />
                      </div>
                    )
                  })}
                </div>
              )}
            </Panel>
          </div>

          <Panel title="Project details" icon={Folder}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="table-header">
                    <th className="px-4 py-3 text-left">Project</th>
                    <th className="px-4 py-3 text-left">Status</th>
                    <th className="px-4 py-3 text-left">Tasks</th>
                    <th className="px-4 py-3 text-left">Overdue</th>
                    <th className="px-4 py-3 text-left">Docs</th>
                    <th className="px-4 py-3 text-left">Due</th>
                  </tr>
                </thead>
                <tbody>
                  {report.projectRows.map((project) => (
                    <tr key={project.id} className="border-b border-border-light last:border-b-0">
                      <td className="px-4 py-3 font-bold"><Link to={`/projects/${project.id}`} className="text-primary hover:underline">{project.name}</Link></td>
                      <td className="px-4 py-3 text-text-secondary">{project.status || '—'}</td>
                      <td className="px-4 py-3 text-text-primary">{project.tasksCompleted}/{project.tasksTotal}</td>
                      <td className="px-4 py-3">{project.overdueTasks > 0 ? <span className="badge badge-danger">{project.overdueTasks}</span> : <span className="text-text-secondary">0</span>}</td>
                      <td className="px-4 py-3 text-text-secondary">{project.documents}</td>
                      <td className="px-4 py-3 text-text-secondary">{fmtDate(project.dueDate)}{project.overdue && <span className="badge badge-danger ml-2">Overdue</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <div className="flex items-start gap-3 rounded-2xl border border-border-light bg-brand-lemon/60 px-5 py-4 text-sm text-text-secondary">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <p>
              <span className="font-bold text-text-primary">Not shown on purpose:</span> monthly completion trends and average completion time.
              The backend does not record task completion dates, so those figures can&rsquo;t be calculated honestly.
            </p>
          </div>
          {totals.overdueTasks + totals.overdueProjects > 0 && (
            <p className="flex items-center gap-2 text-xs text-red-700"><AlertTriangle className="h-3.5 w-3.5" /> {totals.overdueTasks} overdue task{totals.overdueTasks === 1 ? '' : 's'} and {totals.overdueProjects} overdue project{totals.overdueProjects === 1 ? '' : 's'}.</p>
          )}
        </div>
      )}
    </div>
  )
}

export default Reports
