import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Activity, ArrowLeft, ArrowRight, BookOpen, Bot, Calendar, CheckCircle, Code2, FileText, Folder, Layers, ListChecks, RefreshCw, ShieldCheck, User, Zap } from 'lucide-react'
import StatusBadge from '../components/common/StatusBadge'
import ProgressBar from '../components/common/ProgressBar'
import AnalysisResults from '../components/analysis/AnalysisResults'
import PlanResults from '../components/plan/PlanResults'
import { EmptyState, ErrorState, Skeleton } from '../components/common/States'
import apiService from '../services/api'
import { asList, fmtBytes, fmtDateTime, timeAgo } from '../utils/format'
import { buildActivity, latestRunByAgent } from '../utils/activityModel'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'requirements', label: 'Requirements' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'agents', label: 'AI Agents' },
  { id: 'documents', label: 'Documents' },
  { id: 'activity', label: 'Activity' },
]

const DOC_STATUS = { COMPLETED: 'badge-success', FAILED: 'badge-danger' }
const RUN_BADGE = { COMPLETED: 'badge-success', FAILED: 'badge-danger', PROCESSING: 'badge-warning' }
const EVENT_ICON = { project: Folder, document: FileText, run: Bot }

function Tile({ icon: Icon, label, value, hint }) {
  return (
    <div className="card lift group flex items-center gap-3 p-4">
      <span className="bt-icon-bubble h-11 w-11 shrink-0"><Icon className="h-5 w-5" /></span>
      <div className="min-w-0">
        <p className="text-2xl font-extrabold tabular-nums text-text-primary">{value}</p>
        <p className="truncate text-xs font-bold uppercase tracking-wide text-text-secondary">{label}</p>
        {hint && <p className="truncate text-xs text-text-secondary">{hint}</p>}
      </div>
    </div>
  )
}

function AgentRow({ icon: Icon, name, stage, status, detail }) {
  return (
    <div className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
      <span className="bt-icon-bubble h-11 w-11 shrink-0"><Icon className="h-5 w-5" /></span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-extrabold text-text-primary">{name}</p>
        <p className="text-xs text-text-secondary">{stage}</p>
        {detail && <p className="mt-1 text-xs text-text-secondary">{detail}</p>}
      </div>
      <span className={`badge self-start sm:self-center ${RUN_BADGE[status] || 'bg-gray-100 text-text-secondary'}`}>
        {status === 'PROCESSING' ? 'Running' : status === 'COMPLETED' ? 'Completed' : status === 'FAILED' ? 'Failed' : 'Not run yet'}
      </span>
    </div>
  )
}

function ProjectDetails() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')
  const [data, setData] = useState({ project: null, analysis: null, plan: null, architecture: null, documents: [], runs: [], developerRuns: null, qaRuns: null })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async (isCancelled = () => false) => {
    setLoading(true)
    try {
      const project = await apiService.projects.getById(id)
      const [analysis, plan, architecture, documents, runs, developerRuns, qaRuns] = await Promise.all([
        apiService.requirements.getAnalysis(id).catch(() => null),
        apiService.projectManager.get(id).catch(() => null),
        apiService.architect.get(id).catch(() => null),
        apiService.documents.getForProject(id).catch(() => []),
        apiService.requirements.getRuns(id).catch(() => []),
        apiService.developer.getRuns(id).catch(() => null),
        apiService.qa.getRuns(id).catch(() => null),
      ])
      if (isCancelled()) return
      setData({ project, analysis, plan, architecture, documents: asList(documents), runs: asList(runs), developerRuns: Array.isArray(developerRuns) ? developerRuns : asList(developerRuns, 'runs'), qaRuns: Array.isArray(qaRuns) ? qaRuns : asList(qaRuns, 'runs') })
      setError('')
    } catch (requestError) {
      if (!isCancelled()) setError(requestError.message)
    } finally {
      if (!isCancelled()) setLoading(false)
    }
  }, [id])

  useEffect(() => {
    let cancelled = false
    load(() => cancelled)
    return () => { cancelled = true }
  }, [load])

  const { project, analysis, plan, architecture, documents, runs, developerRuns, qaRuns } = data
  const tasks = useMemo(() => asList(plan?.tasks), [plan])
  const byStatus = useMemo(() => tasks.reduce((acc, task) => ({ ...acc, [task.status]: (acc[task.status] || 0) + 1 }), {}), [tasks])
  const activity = useMemo(() => buildActivity(project, documents, runs), [project, documents, runs])
  const latest = useMemo(() => latestRunByAgent(runs), [runs])

  if (loading && !project) {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading project">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-44" />
        <Skeleton className="h-80" />
      </div>
    )
  }

  if (!project) {
    return (
      <div>
        <ErrorState title="Project not available" message={error || 'Project not found'} onRetry={() => load()} retrying={loading} />
        <div className="mt-4 text-center">
          <button onClick={() => navigate('/projects')} className="btn-secondary">Back to Projects</button>
        </div>
      </div>
    )
  }

  const requirementsCount = analysis?.functional_requirements?.length ?? 0
  const planStatus = plan?.plan ? 'COMPLETED' : plan?.status === 'PROCESSING' ? 'PROCESSING' : plan?.status === 'FAILED' ? 'FAILED' : null
  const architectureStatus = architecture?.hld ? 'COMPLETED' : architecture?.status === 'PROCESSING' ? 'PROCESSING' : architecture?.status === 'FAILED' ? 'FAILED' : null
  const requirementRun = latest['Requirements Analyst AI']
  const requirementStatus = analysis?.latest_agent_run?.status === 'COMPLETED' ? 'COMPLETED' : requirementRun?.status || null

  return (
    <div>
      <button
        onClick={() => navigate('/projects')}
        className="mb-5 flex items-center gap-2 text-sm font-bold text-text-secondary transition-colors hover:text-text-primary"
      >
        <ArrowLeft className="h-5 w-5" />
        Back to Projects
      </button>

      <div className="bt-hero mb-6 p-6">
        <div className="relative z-10 mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
          <div className="min-w-0 flex-1">
            <h1 className="mb-2 font-extrabold text-text-primary">{project.name}</h1>
            <p className="text-text-secondary">{project.description || 'No description provided.'}</p>
          </div>
          <div className="flex items-center gap-3">
            <button type="button" onClick={() => load()} disabled={loading} aria-label="Refresh project" className="btn-secondary flex items-center px-2.5 py-2"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></button>
            <StatusBadge status={project.status} />
          </div>
        </div>

        <div className="relative z-10 grid grid-cols-2 gap-6 md:grid-cols-4">
          <div>
            <p className="mb-1 flex items-center gap-1.5 text-sm text-text-secondary"><User className="h-3.5 w-3.5" />Manager</p>
            <p className="font-bold text-text-primary">{project.manager || '—'}</p>
          </div>
          <div>
            <p className="mb-1 flex items-center gap-1.5 text-sm text-text-secondary"><BookOpen className="h-3.5 w-3.5" />Requirements</p>
            <p className="font-bold text-text-primary">{requirementsCount}</p>
          </div>
          <div>
            <p className="mb-1 flex items-center gap-1.5 text-sm text-text-secondary"><Calendar className="h-3.5 w-3.5" />Start Date</p>
            <p className="font-bold text-text-primary">{project.start_date || '—'}</p>
          </div>
          <div>
            <p className="mb-1 flex items-center gap-1.5 text-sm text-text-secondary"><Calendar className="h-3.5 w-3.5" />Due Date</p>
            <p className="font-bold text-text-primary">{project.due_date || '—'}</p>
          </div>
        </div>

        <div className="relative z-10 mt-6">
          <div className="mb-1.5 flex items-center justify-between text-xs font-bold text-text-secondary">
            <span>Overall progress</span>
            <span>{tasks.length ? `${byStatus.COMPLETED || 0}/${tasks.length} tasks done` : 'No plan generated yet'}</span>
          </div>
          <ProgressBar progress={project.progress || 0} size="lg" />
        </div>
      </div>

      <div className="card">
        <div className="flex overflow-x-auto border-b border-border-light" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`whitespace-nowrap border-b-[3px] px-5 py-3.5 text-sm font-bold transition-colors ${
                activeTab === tab.id
                  ? 'border-brand-deep bg-brand-soft/60 text-text-primary'
                  : 'border-transparent text-text-secondary hover:bg-brand-soft/30 hover:text-text-primary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Tile icon={BookOpen} label="Requirements" value={requirementsCount} hint={analysis ? `${analysis.user_stories?.length ?? 0} user stories` : 'Not analysed yet'} />
                <Tile icon={ListChecks} label="Tasks" value={tasks.length} hint={tasks.length ? `${byStatus.IN_PROGRESS || 0} in progress · ${byStatus.TODO || 0} to do` : 'No plan yet'} />
                <Tile icon={Layers} label="Sprints" value={asList(plan?.sprints).length} hint={`${asList(plan?.milestones).length} milestones`} />
                <Tile icon={FileText} label="Documents" value={documents.length} hint={`${documents.filter((doc) => doc.processing_status === 'COMPLETED').length} processed`} />
              </div>
              <div>
                <h3 className="mb-2 font-extrabold text-text-primary">Project Description</h3>
                <p className="text-text-secondary">{project.description || 'No description provided.'}</p>
              </div>
              <div>
                <h3 className="mb-2 font-extrabold text-text-primary">Key Information</h3>
                <ul className="space-y-2 text-sm text-text-secondary">
                  <li>Status: <span className="font-bold text-text-primary">{project.status}</span></li>
                  <li>Manager: <span className="font-bold text-text-primary">{project.manager || '—'}</span></li>
                  <li>Duration: <span className="font-bold text-text-primary">{project.start_date || '—'} to {project.due_date || '—'}</span></li>
                  {project.created_at && <li>Created: <span className="font-bold text-text-primary">{fmtDateTime(project.created_at)}</span></li>}
                </ul>
              </div>
            </div>
          )}

          {activeTab === 'requirements' && (
            <AnalysisResults analysis={analysis} />
          )}

          {activeTab === 'tasks' && <PlanResults plan={plan} />}

          {activeTab === 'agents' && (
            <div className="space-y-4">
              <AgentRow icon={BookOpen} name="Requirements Analyst AI" stage="Reads the SRS and extracts requirements" status={requirementStatus}
                detail={requirementRun ? `Last run ${timeAgo(requirementRun.completed_at || requirementRun.started_at)}` : documents.length ? 'SRS uploaded, ready to analyse' : 'Upload an SRS in Documents first'} />
              <AgentRow icon={Zap} name="Project Manager AI" stage="Plans tasks, sprints and milestones" status={planStatus}
                detail={plan?.plan?.created_at ? `Generated ${timeAgo(plan.plan.created_at)} · ${tasks.length} tasks` : 'Needs completed requirements'} />
              <AgentRow icon={Layers} name="System Architect AI" stage="Designs components, APIs and data" status={architectureStatus}
                detail={architecture?.hld ? 'High-level and low-level design available' : 'Needs a generated project plan'} />
              <AgentRow icon={Code2} name="Developer AI" stage="Implements planned tasks as code" status={developerRuns?.length ? 'COMPLETED' : null}
                detail={developerRuns === null ? 'Run history unavailable' : `${developerRuns.length} run${developerRuns.length === 1 ? '' : 's'} recorded`} />
              <AgentRow icon={ShieldCheck} name="QA AI" stage="Tests generated code and reports defects" status={qaRuns?.length ? 'COMPLETED' : null}
                detail={qaRuns === null ? 'Run history unavailable' : `${qaRuns.length} run${qaRuns.length === 1 ? '' : 's'} recorded`} />
              <Link to="/agents" className="btn-primary inline-flex items-center gap-2">Open AI Agents <ArrowRight className="h-4 w-4" /></Link>
            </div>
          )}

          {activeTab === 'documents' && (
            documents.length === 0 ? (
              <EmptyState icon={FileText} title="No documents uploaded" hint="Upload an SRS PDF so the Requirements Analyst has something to read." to="/documents" cta="Go to Documents" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-sm">
                  <thead><tr className="table-header">
                    <th className="px-4 py-3 text-left">Document</th><th className="px-4 py-3 text-left">Type</th>
                    <th className="px-4 py-3 text-left">Uploaded</th><th className="px-4 py-3 text-left">Size</th><th className="px-4 py-3 text-left">Processing</th>
                  </tr></thead>
                  <tbody>
                    {documents.map((doc) => (
                      <tr key={doc.id} className="border-b border-border-light last:border-b-0">
                        <td className="px-4 py-3 font-bold text-text-primary">{doc.filename}</td>
                        <td className="px-4 py-3 text-text-secondary">{doc.file_type || '—'}</td>
                        <td className="px-4 py-3 text-text-secondary">{doc.upload_time ? new Date(doc.upload_time).toLocaleDateString() : '—'}</td>
                        <td className="px-4 py-3 text-text-secondary">{fmtBytes(doc.file_size)}</td>
                        <td className="px-4 py-3"><span className={`badge ${DOC_STATUS[doc.processing_status] || 'badge-warning'}`}>{doc.processing_status || 'UNKNOWN'}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}

          {activeTab === 'activity' && (
            activity.length === 0 ? (
              <EmptyState icon={Activity} title="No activity recorded yet" hint="Uploads and agent runs for this project will appear here." />
            ) : (
              <ol className="relative space-y-5 border-l-2 border-brand-deep/70 pl-6">
                {activity.map((event) => {
                  const Icon = EVENT_ICON[event.kind] || Activity
                  return (
                    <li key={event.id} className="relative">
                      <span className="bt-icon-bubble absolute -left-[2.35rem] top-0 h-8 w-8 rounded-full"><Icon className="h-4 w-4" /></span>
                      <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-start">
                        <div className="min-w-0">
                          <p className="text-sm font-bold text-text-primary">{event.title}</p>
                          {event.detail && <p className="text-sm text-text-secondary">{event.detail}</p>}
                        </div>
                        <div className="flex shrink-0 items-center gap-2 text-xs text-text-secondary">
                          {event.status && <span className={`badge ${RUN_BADGE[event.status] || 'bg-gray-100 text-text-secondary'}`}>{event.status}</span>}
                          <span title={fmtDateTime(event.at)}>{timeAgo(event.at)}</span>
                        </div>
                      </div>
                    </li>
                  )
                })}
              </ol>
            )
          )}
        </div>
      </div>
    </div>
  )
}

export default ProjectDetails
