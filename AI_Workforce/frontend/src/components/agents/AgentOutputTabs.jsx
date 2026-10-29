import { useRef } from 'react'
import { AlertCircle, Check, Inbox } from 'lucide-react'

const STATE_LABEL = {
  NOT_STARTED: 'Not started',
  PROCESSING: 'Running',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
}

function StepMarker({ state, step }) {
  return (
    <span className="agent-step" data-state={state} aria-hidden="true">
      {state === 'COMPLETED' ? <Check className="w-4 h-4" /> : state === 'FAILED' ? <AlertCircle className="w-4 h-4" /> : state === 'PROCESSING' ? <span className="agent-spinner" /> : step}
    </span>
  )
}

function AgentOutputTabs({ tabs, activeId, onChange }) {
  const refs = useRef({})

  const handleKeyDown = (event, index) => {
    const last = tabs.length - 1
    let next = null
    if (event.key === 'ArrowRight') next = index === last ? 0 : index + 1
    if (event.key === 'ArrowLeft') next = index === 0 ? last : index - 1
    if (event.key === 'Home') next = 0
    if (event.key === 'End') next = last
    if (next === null) return
    event.preventDefault()
    onChange(tabs[next].id)
    refs.current[tabs[next].id]?.focus()
  }

  return (
    <section className="card mb-8 overflow-hidden" aria-label="Agent outputs">
      <div className="border-b border-border-light px-5 pt-4 pb-0 flex items-center justify-between gap-3">
        <h2 className="text-base font-bold text-text-primary pb-3">Agent Outputs</h2>
        <p className="text-xs text-text-secondary pb-3 hidden sm:block">Select an agent to review its result</p>
      </div>

      <div className="agent-tablist border-b border-border-light" role="tablist" aria-label="Agent outputs">
        {tabs.map((tab, index) => {
          const selected = tab.id === activeId
          return (
            <button
              key={tab.id}
              ref={(node) => { refs.current[tab.id] = node }}
              id={`agent-tab-${tab.id}`}
              role="tab"
              type="button"
              aria-selected={selected}
              aria-controls={`agent-panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(tab.id)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              className="agent-tab"
            >
              <StepMarker state={tab.state} step={index + 1} />
              <span className="min-w-0">
                <span className="block text-sm font-semibold truncate">{tab.label}</span>
                <span className="agent-pill block" data-state={tab.state}>{STATE_LABEL[tab.state]}</span>
              </span>
            </button>
          )
        })}
      </div>

      {tabs.map((tab) => (
        <div
          key={tab.id}
          id={`agent-panel-${tab.id}`}
          role="tabpanel"
          aria-labelledby={`agent-tab-${tab.id}`}
          hidden={tab.id !== activeId}
          className="agent-panel p-5 sm:p-6"
        >
          {tab.content || (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border-light bg-bg-light/60 px-4 py-10 text-center">
              <div className="mb-3 rounded-full bg-primary-light p-3"><Inbox className="h-5 w-5 text-primary" /></div>
              <p className="text-sm font-semibold text-text-primary">{tab.emptyTitle}</p>
              <p className="mt-1 max-w-sm text-xs text-text-secondary">{tab.emptyHint}</p>
            </div>
          )}
        </div>
      ))}
    </section>
  )
}

export default AgentOutputTabs
