import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageCircle, Zap, BookOpen, CheckCircle, Play, AlertCircle, Layers } from 'lucide-react'
import { agents } from '../data/agents'
import apiService from '../services/api'
import AnalysisResults from '../components/analysis/AnalysisResults'
import PlanResults from '../components/plan/PlanResults'
import ArchitectureResults from '../components/architecture/ArchitectureResults'

const ARCHITECT_AGENT = {
  id: 'system-architect',
  name: 'System Architect / Design AI',
  description: 'Turns the validated requirements and project plan into a high-level and low-level design: components, APIs, database schema, sequence flows and decisions.',
  icon: 'architect',
}

// The System Architect sits right after the Project Manager in the pipeline.
const withArchitect = (list) => {
  const index = list.findIndex((agent) => agent.icon === 'project')
  const at = index === -1 ? list.length : index + 1
  return [...list.slice(0, at), ARCHITECT_AGENT, ...list.slice(at)]
}

function AIAgents() {
  const [projects, setProjects] = useState([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [runs, setRuns] = useState([])
  const [analysis, setAnalysis] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [plan, setPlan] = useState(null)
  const [isPlanning, setIsPlanning] = useState(false)
  const [architecture, setArchitecture] = useState(null)
  const [isArchitecting, setIsArchitecting] = useState(false)
  const [error, setError] = useState('')

  const loadAgentState = async (projectId) => {
    if (!projectId) return
    try {
      const [runList, result, planResult, architectureResult] = await Promise.all([
        apiService.requirements.getRuns(projectId),
        apiService.requirements.getAnalysis(projectId),
        apiService.projectManager.get(projectId).catch(() => null),
        apiService.architect.get(projectId).catch(() => null),
      ])
      setRuns(runList)
      setAnalysis(result)
      setPlan(planResult)
      setArchitecture(architectureResult)
      setError('')
    } catch (requestError) {
      setRuns([])
      setAnalysis(null)
      setPlan(null)
      setArchitecture(null)
      if (!requestError.message.includes('404')) setError(requestError.message)
    }
  }

  useEffect(() => {
    apiService.projects.getAll()
      .then((items) => {
        setProjects(items)
        if (items.length) setSelectedProjectId(String(items[0].id))
      })
      .catch((requestError) => setError(requestError.message))
  }, [])

  useEffect(() => { loadAgentState(selectedProjectId) }, [selectedProjectId])

  // If a plan is still being generated (for example after a page reload), keep checking.
  useEffect(() => {
    if (plan?.status !== 'PROCESSING' || isPlanning) return undefined
    const timer = setInterval(() => loadAgentState(selectedProjectId), 4000)
    return () => clearInterval(timer)
  }, [plan?.status, isPlanning, selectedProjectId])

  // Same for the architecture.
  useEffect(() => {
    if (architecture?.status !== 'PROCESSING' || isArchitecting) return undefined
    const timer = setInterval(() => loadAgentState(selectedProjectId), 4000)
    return () => clearInterval(timer)
  }, [architecture?.status, isArchitecting, selectedProjectId])

  const requirementRun = runs.find((run) => run.agent_name === 'Requirements Analyst AI')
  const requirementStatus = requirementRun?.status || 'READY'
  const requirementsReady = analysis?.latest_agent_run?.status === 'COMPLETED'
  const planStatus = isPlanning ? 'PROCESSING' : (plan?.status && plan.status !== 'NOT_GENERATED' ? plan.status : 'READY')
  const planReady = Boolean(plan?.plan)
  const architectureStatus = isArchitecting ? 'PROCESSING' : (architecture?.status && architecture.status !== 'NOT_GENERATED' ? architecture.status : 'READY')

  const handleAnalyze = async () => {
    if (!selectedProjectId) {
      setError('Create a project and upload an SRS before analysis.')
      return
    }
    setIsAnalyzing(true)
    setError('')
    try {
      const result = await apiService.requirements.analyze(selectedProjectId)
      setAnalysis(result)
      await loadAgentState(selectedProjectId)
    } catch (requestError) {
      setError(requestError.message)
      await loadAgentState(selectedProjectId)
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleGeneratePlan = async () => {
    if (!selectedProjectId) return
    setIsPlanning(true)
    setError('')
    try {
      setPlan(await apiService.projectManager.run(selectedProjectId))
      await loadAgentState(selectedProjectId)
    } catch (requestError) {
      setError(requestError.message)
      await loadAgentState(selectedProjectId)
    } finally {
      setIsPlanning(false)
    }
  }

  const handleGenerateArchitecture = async () => {
    if (!selectedProjectId) return
    setIsArchitecting(true)
    setError('')
    try {
      setArchitecture(await apiService.architect.run(selectedProjectId))
      await loadAgentState(selectedProjectId)
    } catch (requestError) {
      // Reload first: a successful reload clears the error banner, and this failure must stay visible.
      await loadAgentState(selectedProjectId)
      setError(requestError.message)
    } finally {
      setIsArchitecting(false)
    }
  }

  const getAgentIcon = (iconName) => ({
    requirement: <BookOpen className="w-8 h-8" />,
    project: <Zap className="w-8 h-8" />,
    architect: <Layers className="w-8 h-8" />,
    developer: <CheckCircle className="w-8 h-8" />,
    qa: <CheckCircle className="w-8 h-8" />,
  }[iconName] || <MessageCircle className="w-8 h-8" />)

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div><h1 className="text-3xl font-bold text-text-primary mb-2">AI Agents Hub</h1><p className="text-text-secondary">Run the Requirements Analyst on your SRS, then the Project Manager to plan the work and the System Architect to design it</p></div>
        <label className="text-sm text-text-secondary">Project
          <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} className="input-field ml-3">
            {!projects.length && <option value="">No projects</option>}
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </label>
      </div>

      {error && <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2"><AlertCircle className="w-4 h-4" />{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        {withArchitect(agents).map((agent) => {
          const isRequirements = agent.icon === 'requirement'
          const isProject = agent.icon === 'project'
          const isArchitect = agent.icon === 'architect'
          const isDeveloper = agent.icon === 'developer'
          const isLive = isRequirements || isProject || isArchitect
          const status = isRequirements ? requirementStatus : isProject ? planStatus : isArchitect ? architectureStatus : 'NOT IMPLEMENTED'
          return (
            <div key={agent.id} className="card p-6 flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <div className="bg-primary-light p-3 rounded-lg text-primary">{getAgentIcon(agent.icon)}</div>
                <div className={`w-3 h-3 rounded-full ${isLive && status === 'FAILED' ? 'bg-red-500' : isLive && status === 'PROCESSING' ? 'bg-yellow-500' : 'bg-green-500'}`} />
              </div>
              <h3 className="font-bold text-text-primary mb-2">{agent.name}</h3>
              <p className="text-text-secondary text-sm mb-4 flex-1">{agent.description}</p>
              {isRequirements ? (
                <button onClick={handleAnalyze} disabled={isAnalyzing || !selectedProjectId || requirementStatus === 'PROCESSING'} className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-60">
                  <Play className="w-4 h-4" /> {isAnalyzing || requirementStatus === 'PROCESSING' ? 'Analyzing...' : requirementStatus === 'COMPLETED' ? 'Run Again' : 'Analyze Requirements'}
                </button>
              ) : isProject ? (
                <button onClick={handleGeneratePlan} disabled={isPlanning || !selectedProjectId || !requirementsReady || planStatus === 'PROCESSING'} className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-60">
                  <Play className="w-4 h-4" /> {isPlanning || planStatus === 'PROCESSING' ? 'Generating plan...' : plan?.plan ? 'Regenerate Plan' : 'Generate Project Plan'}
                </button>
              ) : isArchitect ? (
                <button onClick={handleGenerateArchitecture} disabled={isArchitecting || !selectedProjectId || !planReady || architectureStatus === 'PROCESSING'} className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-60">
                  <Play className="w-4 h-4" /> {isArchitecting || architectureStatus === 'PROCESSING' ? 'Designing architecture...' : architecture?.hld ? 'Regenerate Architecture' : 'Generate Architecture'}
                </button>
              ) : isDeveloper ? (
                <Link to="/developer" className="btn-primary w-full flex items-center justify-center gap-2"><Play className="w-4 h-4" /> Open Developer Workspace</Link>
              ) : <button disabled className="btn-secondary w-full opacity-60">Available later</button>}
              <span className="text-xs text-text-secondary mt-2 text-center">
                {isProject && !requirementsReady ? 'Run the Requirements Analyst first' : isArchitect && !planReady ? 'Generate the project plan first' : isDeveloper ? 'Implements planned tasks as tested code' : `Status: ${status}`}
              </span>
            </div>
          )
        })}
      </div>

      {analysis?.latest_agent_run?.status === 'COMPLETED' && (
        <div className="card p-6 mb-8">
          <h2 className="text-lg font-bold text-text-primary mb-4">Latest Requirements Analysis</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <Metric label="Functional requirements" value={analysis.functional_requirements.length} />
            <Metric label="User stories" value={analysis.user_stories.length} />
            <Metric label="Acceptance criteria" value={analysis.acceptance_criteria.length} />
            <Metric label="Ambiguities" value={analysis.ambiguities.length} />
          </div>
          <AnalysisResults analysis={analysis} />
        </div>
      )}

      {plan?.plan && (
        <div className="card p-6 mb-8">
          <h2 className="text-lg font-bold text-text-primary mb-4">Project Plan</h2>
          <PlanResults plan={plan} />
        </div>
      )}

      {architecture?.status === 'FAILED' && !architecture.hld && architecture.latest_agent_run?.error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2"><AlertCircle className="w-4 h-4 shrink-0" />The last attempt to generate the architecture failed: {architecture.latest_agent_run.error}</div>
      )}

      {architecture?.hld && (
        <div className="card p-6 mb-8">
          <h2 className="text-lg font-bold text-text-primary mb-4">System Architecture</h2>
          <ArchitectureResults architecture={architecture} projectName={projects.find((p) => String(p.id) === String(selectedProjectId))?.name} />
        </div>
      )}

      <div className="card p-6">
        <h2 className="text-lg font-bold text-text-primary mb-6">Agent Activity</h2>
        {!runs.length && <p className="text-sm text-text-secondary">No agent runs for this project yet.</p>}
        <div className="space-y-4">
          {runs.map((run) => (
            <div key={run.id} className="flex items-start gap-4 pb-4 border-b border-border-light last:border-b-0">
              <div className="flex-1"><p className="font-medium text-text-primary text-sm">{run.agent_name}</p><p className="text-text-secondary text-sm mt-1">{run.error || `${run.status}${run.output_summary?.requirements_generated ? ` — ${run.output_summary.requirements_generated} requirements generated` : ''}${run.output_summary?.tasks_generated ? ` — ${run.output_summary.tasks_generated} tasks planned` : ''}${run.output_summary?.components ? ` — ${run.output_summary.components} components, ${run.output_summary.apis} APIs designed` : ''}`}</p></div>
              <p className="text-xs text-text-secondary whitespace-nowrap">{run.completed_at ? new Date(run.completed_at).toLocaleString() : 'In progress'}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value }) {
  return <div className="bg-bg-light rounded-lg p-4"><p className="text-2xl font-bold text-primary">{value}</p><p className="text-xs text-text-secondary mt-1">{label}</p></div>
}

export default AIAgents