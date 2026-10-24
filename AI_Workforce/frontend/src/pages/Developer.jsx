import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, ArrowLeft, ChevronDown, ChevronUp, Code2, Download, ExternalLink, Maximize2, Minimize2, Moon, Play, RefreshCw, Square, Sun, Terminal } from 'lucide-react'
import apiService from '../services/api'
import CodeEditor from '../components/developer/CodeEditor'
import FileTree from '../components/developer/FileTree'
import RunPanel from '../components/developer/RunPanel'
import TaskList from '../components/developer/TaskList'
import { buildTree } from '../components/developer/treeUtils'
import { languageFor } from '../components/developer/syntax'
import { applyTheme } from '../utils/theme'

const COMMANDS = [
  { id: 'install', label: 'Install' },
  { id: 'check_imports', label: 'Check imports' },
  { id: 'test', label: 'Run tests' },
]
const PREREQUISITE_PREFIX = 'Complete these prerequisite tasks first'
const RUN_LABEL = { PROCESSING: 'Working', COMPLETED: 'Completed', FAILED: 'Failed' }
const RUN_COLOR = { PROCESSING: 'text-ide-info', COMPLETED: 'text-ide-success', FAILED: 'text-ide-danger' }
const DOT_COLOR = { PROCESSING: 'bg-ide-info animate-pulse', COMPLETED: 'bg-ide-success', FAILED: 'bg-ide-danger' }

const NO_APP = { running: false, log: '', note: '' }

const toolbarButton =
  'flex items-center gap-1.5 px-2.5 py-1 rounded text-[13px] border border-ide-border text-ide-text2 hover:bg-ide-hover disabled:opacity-40 disabled:hover:bg-transparent'

const currentTheme = () => (document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light')

function Developer() {
  const [projects, setProjects] = useState([])
  const [projectId, setProjectId] = useState('')
  const [tasks, setTasks] = useState([])
  const [files, setFiles] = useState([])
  const [tabs, setTabs] = useState([])
  const [activePath, setActivePath] = useState('')
  const [contents, setContents] = useState({})
  const [run, setRun] = useState(null)
  const [commandResult, setCommandResult] = useState(null)
  const [commandBusy, setCommandBusy] = useState('')
  const [startingTask, setStartingTask] = useState('')
  const [forcePrompt, setForcePrompt] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  const [bottomTab, setBottomTab] = useState('run')
  const [panelOpen, setPanelOpen] = useState(true)
  const [panelHeight, setPanelHeight] = useState(260)
  const [theme, setTheme] = useState(currentTheme())
  const [stackInfo, setStackInfo] = useState(null)
  const [stackChoice, setStackChoice] = useState('auto')
  const [appStatus, setAppStatus] = useState(NO_APP)
  const [appBusy, setAppBusy] = useState(false)
  const [fullscreen, setFullscreen] = useState(Boolean(document.fullscreenElement))
  const navigate = useNavigate()

  // Refs let the long-lived callbacks (polling, async loads) always see the latest values.
  const projectRef = useRef('')
  const tabsRef = useRef([])
  const contentsRef = useRef({})
  const centerRef = useRef(null)
  projectRef.current = projectId
  tabsRef.current = tabs
  contentsRef.current = contents

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

  const loadStack = useCallback(async (id) => {
    try {
      setStackInfo(await apiService.developer.getStack(id))
    } catch {
      setStackInfo(null)
    }
  }, [])

  const closeTab = useCallback((path) => {
    const remaining = tabsRef.current.filter((item) => item !== path)
    setTabs(remaining)
    setActivePath((current) => (current === path ? remaining[remaining.length - 1] || '' : current))
  }, [])

  const openFile = useCallback(async (path) => {
    if (!tabsRef.current.includes(path)) setTabs([...tabsRef.current, path])
    setActivePath(path)
    if (contentsRef.current[path] !== undefined) return
    try {
      const data = await apiService.developer.readFile(projectRef.current, path)
      setContents((current) => ({ ...current, [path]: data.content }))
    } catch (requestError) {
      closeTab(path)
      setError(requestError.message)
    }
  }, [closeTab])

  // Re-read the open files after the agent changed them; close tabs whose file was deleted.
  const refreshOpenFiles = useCallback(async () => {
    const id = projectRef.current
    await Promise.all(tabsRef.current.map(async (path) => {
      try {
        const data = await apiService.developer.readFile(id, path)
        setContents((current) => ({ ...current, [path]: data.content }))
      } catch {
        closeTab(path)
      }
    }))
  }, [closeTab])

  // Follow the app theme, including changes made on the Settings page or by the OS.
  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(currentTheme()))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const onChange = () => setFullscreen(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

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
    setTabs([])
    setActivePath('')
    setContents({})
    setCommandResult(null)
    setForcePrompt(null)
    setRun(null)
    setBottomTab('run')
    setError('')
    setStackInfo(null)
    setStackChoice('auto')
    setAppStatus(NO_APP)
    loadStack(projectId)
    apiService.developer.getApp(projectId).then((status) => { if (!cancelled) setAppStatus(status) }).catch(() => {})
    Promise.all([loadWorkspace(projectId), apiService.developer.getRuns(projectId)])
      .then(([, runs]) => { if (!cancelled && runs.length) setRun(runs[0]) })
      .catch((requestError) => { if (!cancelled) setError(requestError.message) })
    return () => { cancelled = true }
  }, [projectId, loadWorkspace, loadStack])

  // Poll while the agent is working.
  useEffect(() => {
    if (!working) return undefined
    const timer = setInterval(async () => {
      try {
        const latest = await apiService.developer.getRun(projectId, run.id)
        setRun(latest)
        if (latest.status !== 'PROCESSING') {
          await loadWorkspace(projectId)
          await loadStack(projectId)
          await refreshOpenFiles()
          const firstChange = latest.changes?.find((change) => change.action !== 'delete')
          if (!tabsRef.current.length && firstChange) await openFile(firstChange.path)
        }
      } catch (requestError) {
        setError(requestError.message)
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [working, run?.id, projectId, loadWorkspace, loadStack, refreshOpenFiles, openFile])

  // While a preview runs, check on it: it stops by itself after a time limit or if the app crashes.
  useEffect(() => {
    if (!appStatus.running) return undefined
    const timer = setInterval(() => {
      apiService.developer.getApp(projectId).then(setAppStatus).catch(() => {})
    }, 5000)
    return () => clearInterval(timer)
  }, [appStatus.running, projectId])

  const startTask = async (task, force = false) => {
    setStartingTask(task.task_id)
    setError('')
    setForcePrompt(null)
    try {
      setRun(await apiService.developer.runTask(projectId, task.task_id, force, stackChoice === 'auto' ? null : stackChoice))
      setAppStatus(NO_APP) // starting a task stops the preview: its files are about to change
      setBottomTab('run')
      setPanelOpen(true)
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
    setBottomTab('terminal')
    setPanelOpen(true)
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

  // Same save path as Settings > Appearance: apply locally at once, then remember it on the server.
  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    applyTheme(next)
    apiService.settings.updatePreferences({ theme: next }).catch(() => {})
  }

  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen?.()
    else document.documentElement.requestFullscreen?.().catch(() => {})
  }

  const exitWorkspace = () => (window.history.state?.idx > 0 ? navigate(-1) : navigate('/dashboard'))

  const startApp = async () => {
    setAppBusy(true)
    setError('')
    try {
      setAppStatus(await apiService.developer.startApp(projectId))
      setBottomTab('app')
      setPanelOpen(true)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setAppBusy(false)
    }
  }

  const stopApp = async () => {
    setAppBusy(true)
    try {
      await apiService.developer.stopApp(projectId)
      setAppStatus(NO_APP)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setAppBusy(false)
    }
  }

  const exportRuns = async () => {
    setExporting(true)
    setError('')
    try {
      await apiService.developer.exportRuns(projectId)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setExporting(false)
    }
  }

  const refresh = async () => {
    setError('')
    try {
      await loadWorkspace(projectId)
      await refreshOpenFiles()
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  // Drag the bar above the bottom panel to resize it.
  const startResize = (event) => {
    event.preventDefault()
    const onMove = (moveEvent) => {
      const rect = centerRef.current.getBoundingClientRect()
      setPanelHeight(Math.min(Math.max(rect.bottom - moveEvent.clientY, 120), Math.max(rect.height - 140, 120)))
      setPanelOpen(true)
    }
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  const commands = COMMANDS.filter((command) => !stackInfo || stackInfo.commands.includes(command.id))

  const statusText = run
    ? `${RUN_LABEL[run.status] || run.status}${run.attempts ? ` · attempt ${run.attempts}` : ''}`
    : 'Ready'

  return (
    <div className="ide h-full flex flex-col bg-ide-bg text-ide-text">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 h-12 flex-shrink-0 border-b border-ide-border">
        <button onClick={exitWorkspace} className={toolbarButton} title="Back to the app">
          <ArrowLeft className="w-3.5 h-3.5" /><span className="hidden md:inline">Exit</span>
        </button>
        <Code2 className="w-5 h-5 text-ide-accent" />
        <span className="font-semibold hidden sm:inline">Developer AI</span>
        <select
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
          className="!bg-ide-panel !text-ide-text border border-ide-border text-[13px] rounded px-2 py-1 max-w-[14rem] focus:outline-none focus:border-ide-accent"
          aria-label="Project"
        >
          {!projects.length && <option value="">No projects</option>}
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
        <span className="flex-1" />
        {run && (
          <span className={`hidden sm:flex items-center gap-2 text-[13px] ${RUN_COLOR[run.status] || ''}`}>
            <span className={`w-2 h-2 rounded-full ${DOT_COLOR[run.status] || 'bg-ide-faint'}`} />{statusText}
          </span>
        )}
        <select
          value={stackInfo?.stack || stackChoice}
          onChange={(event) => setStackChoice(event.target.value)}
          disabled={Boolean(stackInfo?.stack)}
          title={stackInfo?.stack ? 'A project keeps the stack it started with' : 'Choose the stack for the first task, or let it follow the architecture'}
          className="!bg-ide-panel !text-ide-text border border-ide-border text-[13px] rounded px-2 py-1 max-w-[11rem] disabled:opacity-80 focus:outline-none focus:border-ide-accent"
          aria-label="Stack"
        >
          {!stackInfo?.stack && <option value="auto">Stack: auto</option>}
          {(stackInfo?.available || []).map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
        </select>
        {appStatus.running ? (
          <>
            <a href={appStatus.url} target="_blank" rel="noopener noreferrer" className={`${toolbarButton} !text-ide-success`} title="Open the running app in a new tab">
              <ExternalLink className="w-3.5 h-3.5" /><span className="hidden md:inline">Open app</span>
            </a>
            <button onClick={stopApp} disabled={appBusy} className={toolbarButton} title="Stop the app">
              <Square className="w-3.5 h-3.5" /><span className="hidden md:inline">Stop</span>
            </button>
          </>
        ) : (
          <button
            onClick={startApp}
            disabled={working || appBusy || !files.length || stackInfo?.can_start === false}
            className={toolbarButton}
            title="Start the generated app so you can open it"
          >
            <Play className="w-3.5 h-3.5" /><span className="hidden md:inline">{appBusy ? 'Starting...' : 'Run app'}</span>
          </button>
        )}
        <button onClick={exportRuns} disabled={exporting || !run} className={toolbarButton} title="Download all runs of this project as a CSV file">
          <Download className="w-3.5 h-3.5" /><span className="hidden md:inline">{exporting ? 'Exporting...' : 'Export runs'}</span>
        </button>
        <button onClick={refresh} className={toolbarButton} title="Reload tasks and files">
          <RefreshCw className="w-3.5 h-3.5" /><span className="hidden md:inline">Refresh</span>
        </button>
        <button onClick={toggleFullscreen} className={toolbarButton} title={fullscreen ? 'Leave full screen' : 'Full screen'}>
          {fullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
        </button>
        <button onClick={toggleTheme} className={toolbarButton} title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
          {theme === 'dark' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
        </button>
      </div>

      {error && (
        <div className="flex-shrink-0 flex items-center gap-2 px-4 py-2 text-[13px] bg-ide-danger/10 border-b border-ide-danger/40 text-ide-dangertext">
          <AlertCircle className="w-4 h-4 flex-shrink-0" /><span className="flex-1">{error}</span>
          <button onClick={() => setError('')} className="text-ide-dangertext hover:text-ide-text">Dismiss</button>
        </div>
      )}

      {forcePrompt && (
        <div className="flex-shrink-0 flex flex-wrap items-center gap-3 px-4 py-2 text-[13px] bg-ide-warn/10 border-b border-ide-warn/40 text-ide-warn">
          <span className="flex-1">{forcePrompt.message}.</span>
          <button className={toolbarButton} onClick={() => startTask(forcePrompt.task, true)}>Run anyway</button>
          <button className={toolbarButton} onClick={() => setForcePrompt(null)}>Cancel</button>
        </div>
      )}

      {/* Three columns: tasks | editor + panel | files */}
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row overflow-y-auto lg:overflow-hidden">
        <aside className="w-full lg:w-72 flex-shrink-0 max-h-72 lg:max-h-none border-b lg:border-b-0 lg:border-r border-ide-border">
          <TaskList
            tasks={tasks}
            working={working}
            startingTask={startingTask}
            activeTaskId={working ? run?.task_id : null}
            onStart={startTask}
          />
        </aside>

        <section ref={centerRef} className="flex-1 min-w-0 flex flex-col min-h-[32rem] lg:min-h-0">
          <div className="flex-1 min-h-0">
            <CodeEditor tabs={tabs} activePath={activePath} contents={contents} onSelect={setActivePath} onClose={closeTab} />
          </div>

          <div
            onPointerDown={startResize}
            className="h-1 flex-shrink-0 cursor-row-resize bg-ide-hover hover:bg-ide-accent transition-colors"
            title="Drag to resize"
          />

          <div className="flex-shrink-0 flex flex-col bg-ide-bg" style={{ height: panelOpen ? panelHeight : 36 }}>
            <div className="flex items-center h-9 flex-shrink-0 border-b border-ide-border px-2 gap-1">
              {[
                { id: 'run', label: 'Agent run', dot: run && DOT_COLOR[run.status] },
                { id: 'terminal', label: 'Terminal', icon: Terminal },
                { id: 'app', label: 'App', dot: appStatus.running && 'bg-ide-success' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => { setBottomTab(tab.id); setPanelOpen(true) }}
                  className={`flex items-center gap-2 px-3 h-full text-[13px] border-b-2 ${bottomTab === tab.id && panelOpen ? 'border-ide-accent text-ide-text' : 'border-transparent text-ide-muted hover:text-ide-text'}`}
                >
                  {tab.icon && <tab.icon className="w-3.5 h-3.5" />}
                  {tab.dot && <span className={`w-2 h-2 rounded-full ${tab.dot}`} />}
                  {tab.label}
                </button>
              ))}
              <span className="flex-1" />
              {commands.map((command) => (
                <button
                  key={command.id}
                  onClick={() => runCommand(command.id)}
                  disabled={working || Boolean(commandBusy) || !files.length}
                  className={toolbarButton}
                >
                  {commandBusy === command.id ? 'Running...' : command.label}
                </button>
              ))}
              <button onClick={() => setPanelOpen(!panelOpen)} className="p-1 text-ide-muted hover:text-ide-text" title={panelOpen ? 'Collapse panel' : 'Expand panel'}>
                {panelOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
              </button>
            </div>

            {panelOpen && (
              <div className="flex-1 min-h-0 overflow-auto p-3">
                {bottomTab === 'run' && <RunPanel run={run} onOpenFile={openFile} />}
                {bottomTab === 'app' && (
                  <div className="text-[13px]">
                    {appStatus.running ? (
                      <p className="mb-2 text-ide-success">
                        Running at <a className="underline" href={appStatus.url} target="_blank" rel="noopener noreferrer">{appStatus.url}</a>
                        {appStatus.expires_at ? ` · stops automatically at ${new Date(appStatus.expires_at * 1000).toLocaleTimeString()}` : ''}
                      </p>
                    ) : (
                      <p className="mb-2 text-ide-muted">{appStatus.note || 'The app is not running. Press Run app to start it.'}</p>
                    )}
                    {appStatus.log && <pre className="font-mono text-xs text-ide-code whitespace-pre-wrap m-0">{appStatus.log}</pre>}
                  </div>
                )}
                {bottomTab === 'terminal' && (
                  <pre className="text-[13px] font-mono text-ide-code whitespace-pre-wrap m-0">
                    {commandBusy
                      ? `$ ${commandBusy}\nRunning...`
                      : commandResult
                        ? `$ ${commandResult.command}\n${commandResult.output}\n\n${commandResult.ok ? 'Finished successfully' : `Failed (exit code ${commandResult.exit_code})`}`
                        : 'Run Install, Check imports or Run tests to see the output here.'}
                  </pre>
                )}
              </div>
            )}
          </div>
        </section>

        <aside className="w-full lg:w-64 flex-shrink-0 max-h-72 lg:max-h-none flex flex-col min-h-0 border-t lg:border-t-0 lg:border-l border-ide-border">
          <div className="px-3 py-2 border-b border-ide-border text-[11px] uppercase tracking-wide text-ide-muted flex items-center justify-between">
            <span>Files</span>
            <span>{files.length}</span>
          </div>
          <div className="flex-1 overflow-auto min-h-0">
            <FileTree tree={tree} selectedPath={activePath} onSelect={openFile} />
          </div>
        </aside>
      </div>

      {/* Status bar */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 h-6 text-[11px] bg-ide-accent text-white">
        <span>{statusText}</span>
        <span>{activePath ? `${languageFor(activePath)} · ${activePath}` : `${files.length} files`}</span>
      </div>
    </div>
  )
}

export default Developer
