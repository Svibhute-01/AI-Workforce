import { Play } from 'lucide-react'

const DOT = {
  TODO: 'bg-ide-faint',
  IN_PROGRESS: 'bg-ide-info animate-pulse',
  COMPLETED: 'bg-ide-success',
}
const LABEL = { TODO: 'Todo', IN_PROGRESS: 'In progress', COMPLETED: 'Completed' }

function TaskList({ tasks, working, startingTask, activeTaskId, onStart }) {
  const done = tasks.filter((task) => task.status === 'COMPLETED').length
  const percent = tasks.length ? Math.round((done / tasks.length) * 100) : 0

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-3 py-2 border-b border-ide-border">
        <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-ide-muted">
          <span>Tasks</span>
          <span>{done}/{tasks.length} done</span>
        </div>
        <div className="h-1 mt-2 rounded bg-ide-hover overflow-hidden">
          <div className="h-full bg-ide-success transition-all" style={{ width: `${percent}%` }} />
        </div>
      </div>

      <div className="flex-1 overflow-auto p-2 space-y-1.5">
        {!tasks.length && (
          <p className="text-[13px] text-ide-muted p-2">No tasks yet. Generate the project plan on the AI Agents page first.</p>
        )}
        {tasks.map((task) => {
          const active = task.task_id === activeTaskId
          return (
            <div
              key={task.task_id}
              className={`rounded border px-2.5 py-2 ${active ? 'border-ide-accent bg-ide-accent/10' : 'border-ide-border hover:bg-ide-hover/50'}`}
            >
              <div className="flex items-start gap-2">
                <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${DOT[task.status] || DOT.TODO}`} title={LABEL[task.status] || task.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] text-ide-text leading-snug"><span className="text-ide-muted">{task.task_id}</span> {task.title}</p>
                  {task.dependencies?.length > 0 && (
                    <p className="text-[11px] text-ide-muted mt-0.5">After {task.dependencies.join(', ')}</p>
                  )}
                </div>
                <button
                  onClick={() => onStart(task)}
                  disabled={working || Boolean(startingTask)}
                  title={task.status === 'COMPLETED' ? 'Run again' : 'Run this task'}
                  className="flex-shrink-0 w-7 h-7 rounded flex items-center justify-center bg-ide-accent text-white hover:bg-ide-accent-hover disabled:opacity-40 disabled:hover:bg-ide-accent"
                >
                  <Play className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default TaskList
