import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Folder, CheckSquare, CheckCircle, AlertCircle, RefreshCw, Bot, Clock, FileText, ArrowRight,
  Activity, AlertTriangle, Layers, Calendar, Sparkles, Inbox, WifiOff, Code2, ShieldCheck,
  ClipboardList, Info,
} from 'lucide-react'
import apiService from '../services/api'

/* ------------------------------ helpers ------------------------------ */

const greeting = () => {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

const timeAgo = (iso) => {
  if (!iso) return 'Never'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'Just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  if (s < 86400 * 30) return `${Math.floor(s / 86400)}d ago`
  return new Date(iso).toLocaleDateString()
}

const fmtDuration = (sec) => {
  if (sec == null) return '—'
  if (sec < 60) return `${Math.round(sec)}s`
  return `${Math.floor(sec / 60)}m ${Math.round(sec % 60)}s`
}

const fmtDate = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '—')

const STATUS_COLORS = { TODO: '#f59e0b', IN_PROGRESS: '#3b82f6', COMPLETED: '#10b981' }
const PRIORITY_STYLE = {
  HIGH: 'bg-red-50 text-red-700',
  MEDIUM: 'bg-amber-50 text-amber-700',
  LOW: 'bg-emerald-50 text-emerald-700',
}
const RUN_STYLE = {
  COMPLETED: { dot: 'bg-emerald-500', text: 'text-emerald-700', label: 'Completed' },
  FAILED: { dot: 'bg-red-500', text: 'text-red-700', label: 'Failed' },
  PROCESSING: { dot: 'bg-blue-500 animate-pulse', text: 'text-blue-700', label: 'Running' },
}
const runStyle = (s) => RUN_STYLE[s] || RUN_STYLE.PROCESSING
const AGENT_ICON = { requirements_analyst: ClipboardList, project_manager: Layers, developer: Code2, qa: ShieldCheck }
const ATTENTION_STYLE = {
  high: 'border-red-200 bg-red-50 text-red-700',
  medium: 'border-amber-200 bg-amber-50 text-amber-700',
  info: 'border-blue-200 bg-blue-50 text-blue-700',
}

/* ---------------------------- small building blocks ---------------------------- */

const Skeleton = ({ className = '' }) => <div className={`animate-pulse rounded-lg bg-gray-200/70 ${className}`} />

function Card({ title, icon: Icon, action, children, className = '', delay = 0 }) {
  return (
    <section
      className={`card dash-in p-6 transition-shadow duration-200 hover:shadow-md ${className}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="mb-5 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-base font-bold text-text-primary">
          {Icon && <Icon className="h-4 w-4 text-primary" />}
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  )
}

const ViewAll = ({ to, label = 'View all' }) => (
  <Link to={to} className="group flex items-center gap-1 text-sm font-medium text-primary hover:text-primary-dark">
    {label}
    <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
  </Link>
)

function Empty({ icon: Icon = Inbox, title, hint, to, cta }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border-light bg-bg-light/60 px-4 py-8 text-center">
      <div className="mb-3 rounded-full bg-primary-light p-3"><Icon className="h-5 w-5 text-primary" /></div>
      <p className="text-sm font-semibold text-text-primary">{title}</p>
      {hint && <p className="mt-1 max-w-xs text-xs text-text-secondary">{hint}</p>}
      {to && <Link to={to} className="btn-primary mt-4 text-sm">{cta}</Link>}
    </div>
  )
}

function StatTile({ title, value, sub, icon: Icon, tone = 'primary', delay }) {
  const tones = {
    primary: 'bg-primary-light text-primary',
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-emerald-50 text-emerald-600',
    red: 'bg-red-50 text-red-600',
  }
  return (
    <div
      className="card dash-in group p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="mb-1 text-sm text-text-secondary">{title}</p>
          <p className="text-3xl font-bold text-text-primary">{value}</p>
          <p className="mt-1.5 truncate text-xs text-text-secondary">{sub}</p>
        </div>
        <div className={`rounded-xl p-3 transition-transform duration-200 group-hover:scale-110 ${tones[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  )
}

function Bar({ value, color = 'bg-primary' }) {
  return (
    <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
      <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${value ?? 0}%` }} />
    </div>
  )
}

function Donut({ items, total }) {
  const r = 52
  const c = 2 * Math.PI * r
  let offset = 0
  return (
    <svg viewBox="0 0 140 140" className="h-40 w-40 shrink-0">
      <g transform="rotate(-90 70 70)">
        <circle cx="70" cy="70" r={r} fill="none" stroke="#f1f0fb" strokeWidth="16" />
        {items.filter((i) => i.count > 0).map((i) => {
          const len = (i.count / total) * c
          const el = (
            <circle
              key={i.key}
              cx="70" cy="70" r={r} fill="none" strokeWidth="16"
              stroke={STATUS_COLORS[i.key] || '#9ca3af'}
              strokeDasharray={`${len} ${c - len}`}
              strokeDashoffset={-offset}
              className="transition-all duration-700"
            >
              <title>{`${i.label}: ${i.count}`}</title>
            </circle>
          )
          offset += len
          return el
        })}
      </g>
      <text x="70" y="70" textAnchor="middle" fontSize="26" fontWeight="700" fill="#1a1a1a">{total}</text>
      <text x="70" y="88" textAnchor="middle" fontSize="10" fill="#666666">tasks</text>
    </svg>
  )
}

/* ------------------------------ loading / error ------------------------------ */

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Skeleton className="h-72 lg:col-span-2" />
        <Skeleton className="h-72" />
      </div>
      <Skeleton className="h-52" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    </div>
  )
}

function ErrorState({ message, onRetry, retrying }) {
  return (
    <div className="card flex flex-col items-center px-6 py-16 text-center">
      <div className="mb-4 rounded-full bg-red-50 p-4"><WifiOff className="h-7 w-7 text-red-500" /></div>
      <h2 className="text-lg font-bold text-text-primary">Couldn't load your dashboard</h2>
      <p className="mt-1 max-w-md text-sm text-text-secondary">{message}</p>
      <button onClick={onRetry} disabled={retrying} className="btn-primary mt-5 flex items-center gap-2 disabled:opacity-60">
        <RefreshCw className={`h-4 w-4 ${retrying ? 'animate-spin' : ''}`} /> Try again
      </button>
    </div>
  )
}

/* ------------------------------ sections ------------------------------ */

function ProjectProgress({ projects }) {
  if (!projects.length) {
    return <Empty icon={Folder} title="No projects yet" hint="Create a project to start tracking progress." to="/projects" cta="Create project" />
  }
  return (
    <div className="space-y-5">
      {projects.slice(0, 5).map((p) => (
        <Link key={p.id} to={`/projects/${p.id}`} className="group -m-2 block rounded-lg p-2 transition-colors hover:bg-bg-light">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="truncate font-medium text-text-primary group-hover:text-primary">{p.name}</p>
            <span className="shrink-0 text-xs text-text-secondary">
              {p.progress == null ? 'No plan yet' : `${p.tasks_completed}/${p.tasks_total} tasks · ${p.progress}%`}
            </span>
          </div>
          <Bar value={p.progress ?? 0} color={p.overdue_tasks ? 'bg-amber-500' : 'bg-primary'} />
        </Link>
      ))}
    </div>
  )
}

function TaskDistribution({ tasks }) {
  if (!tasks.total) {
    return <Empty icon={CheckSquare} title="No tasks yet" hint="Tasks appear once the Project Manager AI generates a plan." />
  }
  const maxRole = Math.max(...tasks.by_role.map((r) => r.count), 1)
  return (
    <div className="space-y-6">
      <div className="flex flex-col items-center gap-5 sm:flex-row lg:flex-col xl:flex-row">
        <Donut items={tasks.by_status} total={tasks.total} />
        <ul className="w-full space-y-2.5 text-sm">
          {tasks.by_status.map((s) => (
            <li key={s.key} className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-text-secondary">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLORS[s.key] || '#9ca3af' }} />{s.label}
              </span>
              <span className="font-semibold text-text-primary">{s.count}</span>
            </li>
          ))}
          <li className="flex items-center justify-between border-t border-border-light pt-2.5 text-xs text-text-secondary">
            <span>Story points</span>
            <span className="font-semibold text-text-primary">{tasks.completed_story_points}/{tasks.total_story_points}</span>
          </li>
        </ul>
      </div>
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">By priority</p>
        <div className="flex flex-wrap gap-2">
          {tasks.by_priority.map((p) => (
            <span key={p.key} className={`rounded-full px-3 py-1 text-xs font-medium ${PRIORITY_STYLE[p.key] || 'bg-gray-100 text-gray-700'}`}>
              {p.label}: {p.count}
            </span>
          ))}
        </div>
      </div>
      {tasks.by_role.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">By suggested role</p>
          <div className="space-y-2">
            {tasks.by_role.slice(0, 5).map((r) => (
              <div key={r.key} className="flex items-center gap-3 text-xs">
                <span className="w-28 shrink-0 truncate text-text-secondary">{r.label}</span>
                <Bar value={(r.count / maxRole) * 100} color="bg-primary/70" />
                <span className="w-6 text-right font-semibold text-text-primary">{r.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function AgentCard({ agent }) {
  const Icon = AGENT_ICON[agent.key] || Bot
  const idle = agent.total_runs === 0
  const last = agent.last_run_status ? runStyle(agent.last_run_status) : null
  return (
    <div className="group rounded-xl border border-border-light p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md">
      <div className="mb-3 flex items-center gap-3">
        <div className="rounded-lg bg-primary-light p-2.5 transition-transform group-hover:scale-110"><Icon className="h-5 w-5 text-primary" /></div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text-primary">{agent.name}</p>
          <p className="text-xs text-text-secondary">{agent.stage}</p>
        </div>
        {last && <span className={`ml-auto h-2.5 w-2.5 shrink-0 rounded-full ${last.dot}`} title={`Last run: ${last.label}`} />}
      </div>
      {idle ? (
        <p className="rounded-lg bg-bg-light px-3 py-2 text-xs text-text-secondary">No runs recorded yet</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div><p className="text-lg font-bold text-text-primary">{agent.total_runs}</p><p className="text-[11px] text-text-secondary">Runs</p></div>
            <div><p className="text-lg font-bold text-text-primary">{agent.success_rate == null ? '—' : `${agent.success_rate}%`}</p><p className="text-[11px] text-text-secondary">Success</p></div>
            <div><p className="text-lg font-bold text-text-primary">{fmtDuration(agent.avg_duration_seconds)}</p><p className="text-[11px] text-text-secondary">Avg time</p></div>
          </div>
          <p className="mt-3 truncate text-xs text-text-secondary">
            Last run {timeAgo(agent.last_run_at)}{agent.last_project ? ` · ${agent.last_project}` : ''}
            {agent.failed > 0 && <span className="text-red-600"> · {agent.failed} failed</span>}
          </p>
        </>
      )}
    </div>
  )
}

function RecentRuns({ runs }) {
  if (!runs.length) return <Empty icon={Activity} title="No agent activity yet" hint="Run the Requirements Analyst or Project Manager on a project." />
  return (
    <ul className="divide-y divide-border-light">
      {runs.slice(0, 6).map((r) => {
        const st = runStyle(r.status)
        return (
          <li key={r.id} className="flex items-center gap-3 py-2.5 text-sm">
            <span className={`h-2 w-2 shrink-0 rounded-full ${st.dot}`} />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-text-primary">{r.agent_name}</p>
              <p className="truncate text-xs text-text-secondary">{r.project_name}{r.error ? ` · ${r.error}` : ''}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className={`text-xs font-medium ${st.text}`}>{st.label}</p>
              <p className="text-[11px] text-text-secondary">{timeAgo(r.started_at)}</p>
            </div>
          </li>
        )
      })}
    </ul>
  )
}

function RecentProjects({ projects }) {
  if (!projects.length) return <Empty icon={Folder} title="No projects yet" hint="Your newest projects will show up here." to="/projects" cta="Create project" />
  return (
    <ul className="divide-y divide-border-light">
      {projects.slice(0, 5).map((p) => (
        <li key={p.id}>
          <Link to={`/projects/${p.id}`} className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-3 transition-colors hover:bg-bg-light">
            <div className="rounded-lg bg-primary-light p-2"><Folder className="h-4 w-4 text-primary" /></div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-text-primary">{p.name}</p>
              <p className="truncate text-xs text-text-secondary">
                {p.documents} doc{p.documents === 1 ? '' : 's'} · {p.tasks_total} task{p.tasks_total === 1 ? '' : 's'}
                {p.due_date ? ` · due ${fmtDate(p.due_date)}` : ''}
              </p>
            </div>
            <span className={`badge shrink-0 ${p.is_overdue ? 'badge-danger' : 'bg-purple-100 text-primary'}`}>{p.is_overdue ? 'Overdue' : p.status}</span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function RecentTasks({ tasks }) {
  if (!tasks.length) return <Empty icon={CheckSquare} title="No tasks yet" hint="Generate a plan with the Project Manager AI to see tasks here." />
  return (
    <ul className="divide-y divide-border-light">
      {tasks.slice(0, 6).map((t) => (
        <li key={t.id} className="flex items-center gap-3 py-2.5">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: STATUS_COLORS[t.status] || '#9ca3af' }} title={t.status} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-text-primary">{t.title}</p>
            <p className="truncate text-xs text-text-secondary">{t.project_name} · {t.suggested_role} · {t.story_points} pt{t.story_points === 1 ? '' : 's'}</p>
          </div>
          <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${PRIORITY_STYLE[t.priority] || 'bg-gray-100 text-gray-700'}`}>{t.priority || '—'}</span>
        </li>
      ))}
    </ul>
  )
}

function Insights({ insights }) {
  const max = Math.max(...insights.pipeline.map((s) => s.count), 1)
  const { requirements: rq, documents: dc, risks: rk } = insights
  const mini = [
    ['Functional reqs', rq.functional], ['Non-functional', rq.non_functional],
    ['User stories', rq.user_stories], ['Acceptance criteria', rq.acceptance_criteria],
    ['High risks', rk.high_risks], ['Open ambiguities', rk.open_ambiguities],
    ['Blocking deps', rk.blocking_dependencies], ['Docs processed', `${dc.processed}/${dc.total}`],
  ]
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-secondary">SDLC pipeline (projects reaching each stage)</p>
        <div className="space-y-3">
          {insights.pipeline.map((s) => (
            <div key={s.key} className="flex items-center gap-3 text-xs">
              <span className="w-32 shrink-0 text-text-secondary">{s.label}</span>
              <Bar value={(s.count / max) * 100} />
              <span className="w-5 text-right font-semibold text-text-primary">{s.count}</span>
            </div>
          ))}
        </div>
        <div className="mt-5 grid grid-cols-2 gap-2">
          {mini.map(([label, val]) => (
            <div key={label} className="rounded-lg bg-bg-light px-3 py-2">
              <p className="text-base font-bold text-text-primary">{val}</p>
              <p className="text-[11px] text-text-secondary">{label}</p>
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-secondary">Active sprints</p>
        {insights.active_sprints.length === 0 ? (
          <Empty icon={Calendar} title="No sprint in progress" hint="Sprints show here while today falls inside their dates." />
        ) : (
          <div className="space-y-3">
            {insights.active_sprints.map((s) => {
              const pct = s.tasks_total ? Math.round((100 * s.tasks_completed) / s.tasks_total) : 0
              return (
                <div key={`${s.project_id}-${s.sprint_id}`} className="rounded-lg border border-border-light p-3">
                  <p className="truncate text-sm font-medium text-text-primary">{s.name}</p>
                  <p className="mb-2 truncate text-xs text-text-secondary">{s.project_name} · ends {fmtDate(s.end_date)}</p>
                  <div className="flex items-center gap-3 text-xs"><Bar value={pct} /><span className="font-semibold">{s.tasks_completed}/{s.tasks_total}</span></div>
                </div>
              )
            })}
          </div>
        )}
      </div>
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-secondary">Needs attention</p>
        {insights.attention.length === 0 ? (
          <Empty icon={CheckCircle} title="All clear" hint="No overdue work, failed runs or blockers detected." />
        ) : (
          <ul className="space-y-2">
            {insights.attention.map((a, i) => (
              <li key={i} className={`flex gap-2 rounded-lg border px-3 py-2 text-xs ${ATTENTION_STYLE[a.severity] || ATTENTION_STYLE.info}`}>
                {a.severity === 'info' ? <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
                <div className="min-w-0">
                  <p className="font-semibold">{a.title} <span className="font-normal opacity-80">· {a.project_name}</span></p>
                  {a.detail && <p className="opacity-90">{a.detail}</p>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

/* -------------------------------- page -------------------------------- */

function Dashboard() {
  const [data, setData] = useState(null)
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
      setData(summary)
      setError('')
    } catch (e) {
      if (alive.current) setError(e.message || 'Something went wrong while loading the dashboard.')
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

  const name = data?.user_name || localStorage.getItem('userName') || ''
  const t = data?.tasks
  const p = data?.projects
  const noProjects = data && p.total === 0

  return (
    <div className="mx-auto max-w-7xl">
      <style>{`
        @keyframes dashIn { from { opacity: 0; transform: translateY(8px) } to { opacity: 1; transform: none } }
        .dash-in { animation: dashIn .45s ease-out both }
        @media (prefers-reduced-motion: reduce) { .dash-in { animation: none } }
      `}</style>

      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="mb-1 flex items-center gap-2 text-3xl font-bold text-text-primary">
            {greeting()}{name ? `, ${name.split(' ')[0]}` : ''}
            <Sparkles className="h-6 w-6 text-primary" />
          </h1>
          <p className="text-text-secondary">Your AI-powered SDLC at a glance.</p>
        </div>
        <div className="flex items-center gap-3">
          {data && (
            <span className="hidden items-center gap-1.5 text-xs text-text-secondary sm:flex">
              <Clock className="h-3.5 w-3.5" /> Updated {timeAgo(data.generated_at)}
            </span>
          )}
          <button onClick={() => load(true)} disabled={loading || refreshing} className="btn-outline flex items-center gap-2 text-sm disabled:opacity-60">
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </div>

      {loading && !data ? (
        <DashboardSkeleton />
      ) : !data ? (
        <ErrorState message={error} onRetry={() => load()} retrying={loading} />
      ) : (
        <div className="space-y-6">
          {error && (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <span className="flex items-center gap-2"><AlertCircle className="h-4 w-4" /> Refresh failed: {error}. Showing the last loaded data.</span>
              <button onClick={() => load(true)} className="font-medium underline">Retry</button>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile title="Projects" value={p.total} icon={Folder} delay={0}
              sub={p.new_last_7_days ? `${p.new_last_7_days} new in the last 7 days` : 'None created in the last 7 days'} />
            <StatTile title="Tasks" value={t.total} icon={CheckSquare} tone="blue" delay={60}
              sub={t.total ? `${t.in_progress} in progress · ${t.todo} to do · ${t.total_story_points} pts` : 'No plan generated yet'} />
            <StatTile title="Completed" value={t.completed} icon={CheckCircle} tone="green" delay={120}
              sub={t.completion_rate == null ? 'No tasks to measure yet' : `${t.completion_rate}% completion rate`} />
            <StatTile title="Overdue" value={t.overdue + p.overdue} icon={AlertCircle} tone="red" delay={180}
              sub={`${t.overdue} task${t.overdue === 1 ? '' : 's'} · ${p.overdue} project${p.overdue === 1 ? '' : 's'}`} />
          </div>

          {noProjects ? (
            <Card title="Get started" icon={Sparkles}>
              <Empty icon={Folder} title="Welcome — your workspace is empty"
                hint="Create a project, upload an SRS and let the AI agents analyze requirements and plan your sprints."
                to="/projects" cta="Create your first project" />
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <Card title="Project progress" icon={Layers} className="lg:col-span-2" delay={100} action={<ViewAll to="/projects" />}>
                  <ProjectProgress projects={data.project_overview} />
                </Card>
                <Card title="Task distribution" icon={CheckSquare} delay={160} action={<ViewAll to="/tasks" />}>
                  <TaskDistribution tasks={t} />
                </Card>
              </div>

              <Card title="AI agent activity" icon={Bot} delay={200} action={<ViewAll to="/agents" label="Open agents" />}>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {data.agents.map((a) => <AgentCard key={a.key} agent={a} />)}
                </div>
                <div className="mt-6">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-secondary">Recent runs</p>
                  <RecentRuns runs={data.recent_agent_runs} />
                </div>
              </Card>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Card title="Recent projects" icon={Folder} delay={240} action={<ViewAll to="/projects" />}>
                  <RecentProjects projects={data.project_overview} />
                </Card>
                <Card title="Recent tasks" icon={CheckSquare} delay={280} action={<ViewAll to="/tasks" />}>
                  <RecentTasks tasks={data.recent_tasks} />
                </Card>
              </div>

              <Card title="Project & SDLC insights" icon={FileText} delay={320}>
                <Insights insights={data.insights} />
              </Card>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default Dashboard
