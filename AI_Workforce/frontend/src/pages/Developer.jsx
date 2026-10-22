import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertCircle, Code2, Play, RefreshCw, Terminal } from 'lucide-react'
import apiService from '../services/api'
import StatusBadge from '../components/common/StatusBadge'
import FileTree from '../components/developer/FileTree'
import RunPanel from '../components/developer/RunPanel'
import { buildTree } from '../components/developer/treeUtils'

const TASK_LABELS = { TODO: 'Todo', IN_PROGRESS: 'In Progress', COMPLETED: 'Completed' }
const COMMANDS = [
  { id: 'install', label: 'Install' },
  { id: 'check_imports', label: 'Check imports' },
  { id: 'test', label: 'Run tests' },
]
const PREREQUISITE_PREFIX = 'Complete these prerequisite tasks first'

function Developer() {
  const [projects, setProjects] = useState([])
  const [projectId, setProjectId] = useState('')
  const [tasks, setTasks] = useState([])
  const [files, setFiles] = useState([])
  const [selectedPath, setSelectedPath] = useState('')
  const [fileContent, setFileContent] = useState('')
  const [run, setRun] = useState(null)
  const [commandResult, setCommandResult] = useState(null)
  const [commandBusy, setCommandBusy] = useState('')
  const [startingTask, setStartingTask] = useState('')
  const [forcePrompt, setForcePrompt] = useState(null)
  const [error, setError] = useState('')

  const working = run?.status === 'PROCESSING'
  const tree = useMemo(() => buildTree(files), [files])

  const loadWorkspace = useCallback(async (id) => {
    const [taskList, fileList] = await Promise.all([
      apiService.projectManager.getTasks(id).catch(() => []),
      apiService.developer.listFiles(id).then((data) => data.files),
    ])
    setTasks([...taskList].sort((a, b) => a.execution_index - b.execution_index))
    setFiles(fileList)
    return fileList
  }, [])

  const openFile = useCallback(async (path, id = projectId) => {
    setSelectedPath(path)
    try {
      const data = await apiService.developer.readFile(id, path)
      setFileContent(data.content)
    } catch (requestError) {
      setFileContent('')
      setError(requestError.message)
    }
  }, [projectId])

  useEffect(() => {
    apiService.projects.getAll()
      .then((items) => {
        setProjects(items)
        if (items.length) setProjectId(String(items[0].id))
      })
      .catch((requestError) => setError(requestError.message))
  }, [])

  // Load everything for the chosen project, and resume watching a run that is still going.
  useEffect(() => {
    if (!projectId) return undefined
    let cancelled = false
    setSelectedPath('')
    setFileContent('')
    setCommandResult(null)
    setForcePrompt(null)
    setRun(null)
    setError('')
    Promise.all([loadWorkspace(projectId), apiService.developer.getRuns(projectId)])
      .then(([, runs]) => { if (!cancelled && runs.length) setRun(runs[0]) })
      .catch((requestError) => { if (!cancelled) setError(requestError.message) })
    return () => { cancelled = true }
  }, [projectId, loadWorkspace])

  // Poll while the agent is working.
  useEffect(() => {
    if (!working) return undefined
    const timer = setInterval(async () => {
      try {
        const latest = await apiService.developer.getRun(projectId, run.id)
        setRun(latest)
        if (latest.status !== 'PROCESSING') {
          await loadWorkspace(projectId)
          if (selectedPath) await openFile(selectedPath)
        }
      } catch (requestError) {
        setError(requestError.message)
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [working, run?.id, projectId, selectedPath, loadWorkspace, openFile])

  const startTask = async (task, force = false) => {
    setStartingTask(task.task_id)
    setError('')
    setForcePrompt(null)
    try {
      setRun(await apiService.developer.runTask(projectId, task.task_id, force))
      setTasks((current) => current.map((item) => (item.task_id === task.task_id ? { ...item, status: 'IN_PROGRESS' } : item)))
    } catch (requestError) {
      if (requestError.message.startsWith(PREREQUISITE_PREFIX)) {
        setForcePrompt({ task, message: requestError.message })
      } else {
        setError(requestError.message)
      }
    } finally {
      setStartingTask('')
    }
  }

  const runCommand = async (command) => {
    setCommandBusy(command)
    setCommandResult(null)
    setError('')
    try {
      setCommandResult(await apiService.developer.runCommand(projectId, command))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setCommandBusy('')
    }
  }

  const refresh = async () => {
    setError('')
    try {
      await loadWorkspace(projectId)
      if (selectedPath) await openFile(selectedPath)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-2">Developer AI Workspace</h1>
          <p className="text-text-secondary">Pick a planned task. The Developer AI writes the code, installs dependencies, runs the tests and fixes failures before it reports back.</p>
        </div>
        <label className="text-sm text-text-secondary">Project
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)} className="input-field ml-3">
            {!projects.length && <option value="">No projects</option>}
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </label>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />{error}
        </div>
      )}

      {forcePrompt && (
        <div className="mb-6 bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg flex flex-wrap items-center gap-3">
          <span className="flex-1 text-sm">{forcePrompt.message}.</span>
          <button className="btn-outline" onClick={() => startTask(forcePrompt.task, true)}>Run anyway</button>
          <button className="btn-secondary" onClick={() => setForcePrompt(null)}>Cancel</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[22rem_1fr] gap-6">
        <div className="space-y-6">
          <div className="card p-4">
            <h2 className="font-bold text-text-primary mb-3">Tasks</h2>
            {!tasks.length && <p className="text-sm text-text-secondary">No tasks yet. Generate a project plan on the AI Agents page first.</p>}
            <ul className="space-y-3 max-h-80 overflow-auto">
              {tasks.map((task) => (
                <li key={task.task_id} className="border border-border-light rounded-lg p-3">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="text-sm font-medium text-text-primary">{task.task_id}: {task.title}</span>
                    <StatusBadge status={TASK_LABELS[task.status] || task.status} />
                  </div>
                  {task.dependencies?.length > 0 && <p className="text-xs text-text-secondary mb-2">Depends on {task.dependencies.join(', ')}</p>}
                  <button
                    onClick={() => startTask(task)}
                    disabled={working || Boolean(startingTask)}
                    className="btn-primary w-full flex items-center justify-center gap-2 text-sm disabled:opacity-60"
                  >
                    <Play className="w-4 h-4" />
                    {startingTask === task.task_id ? 'Starting...' : task.status === 'COMPLETED' ? 'Implement again' : 'Implement'}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-text-primary flex items-center gap-2"><Code2 className="w-4 h-4" />Files</h2>
              <button onClick={refresh} title="Refresh" className="text-text-secondary hover:text-primary"><RefreshCw className="w-4 h-4" /></button>
            </div>
            <div className="max-h-96 overflow-auto">
              <FileTree tree={tree} selectedPath={selectedPath} onSelect={openFile} />
            </div>
          </div>
        </div>

        <div className="space-y-6 min-w-0">
          <div className="card p-4">
            <h2 className="font-bold text-text-primary mb-3">Agent run</h2>
            <RunPanel run={run} onOpenFile={openFile} />
          </div>

          <div className="card overflow-hidden">
            <div className="px-4 py-2 border-b border-border-light bg-gray-50 text-sm text-text-secondary font-mono truncate">
              {selectedPath || 'Select a file to view it'}
            </div>
            <pre className="text-sm font-mono overflow-auto max-h-[28rem] p-0 m-0">
              {fileContent.split('\n').map((line, index) => (
                <div key={index} className="flex hover:bg-gray-50">
                  <span className="select-none text-right text-text-secondary/60 w-12 pr-3 flex-shrink-0">{selectedPath ? index + 1 : ''}</span>
                  <code className="whitespace-pre pr-4">{line}</code>
                </div>
              ))}
            </pre>
          </div>

          <div className="card overflow-hidden">
            <div className="px-4 py-3 border-b border-border-light flex flex-wrap items-center gap-2">
              <Terminal className="w-4 h-4 text-text-secondary" />
              <h2 className="font-bold text-text-primary mr-auto">Terminal</h2>
              {COMMANDS.map((command) => (
                <button
                  key={command.id}
                  onClick={() => runCommand(command.id)}
                  disabled={working || Boolean(commandBusy) || !files.length}
                  className="btn-outline text-sm disabled:opacity-60"
                >
                  {commandBusy === command.id ? 'Running...' : command.label}
                </button>
              ))}
            </div>
            <pre className="bg-gray-900 text-gray-100 text-sm font-mono p-4 overflow-auto max-h-80 min-h-[6rem] whitespace-pre-wrap">
              {commandBusy
                ? `$ ${commandBusy}\nRunning...`
                : commandResult
                  ? `$ ${commandResult.command}\n${commandResult.output}\n\n${commandResult.ok ? 'Finished successfully' : `Failed (exit code ${commandResult.exit_code})`}`
                  : 'Run install, an import check or the tests to see the output here.'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Developer
