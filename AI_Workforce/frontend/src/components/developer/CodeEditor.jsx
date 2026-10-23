import { useMemo } from 'react'
import { X } from 'lucide-react'
import { highlight, languageFor } from './syntax'

const COLORS = {
  keyword: 'text-ide-syn-keyword',
  string: 'text-ide-syn-string',
  comment: 'text-ide-syn-comment italic',
  number: 'text-ide-syn-number',
  decorator: 'text-ide-syn-decorator',
  name: 'text-ide-syn-name',
  plain: 'text-ide-code',
}

function CodeEditor({ tabs, activePath, contents, onSelect, onClose }) {
  const content = contents[activePath]
  const lines = useMemo(
    () => (content === undefined ? [] : highlight(content, languageFor(activePath))),
    [content, activePath],
  )

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex bg-ide-bg border-b border-ide-border overflow-x-auto flex-shrink-0">
        {tabs.map((path) => (
          <div
            key={path}
            className={`group flex items-center gap-2 pl-3 pr-1.5 py-2 text-[13px] border-r border-ide-border cursor-pointer flex-shrink-0 ${path === activePath ? 'bg-ide-panel text-ide-text border-t-2 border-t-ide-accent -mb-px' : 'text-ide-muted hover:bg-ide-panel/60'}`}
            onClick={() => onSelect(path)}
            title={path}
          >
            <span>{path.split('/').pop()}</span>
            <button
              onClick={(event) => { event.stopPropagation(); onClose(path) }}
              className="w-4 h-4 rounded flex items-center justify-center text-ide-muted hover:bg-ide-hover hover:text-ide-text"
              title="Close"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex-1 overflow-auto bg-ide-panel min-h-0">
        {!activePath && (
          <div className="h-full flex flex-col items-center justify-center text-ide-muted text-sm gap-1 p-6 text-center">
            <p className="text-ide-text font-medium">No file open</p>
            <p>Pick a file from the tree on the right, or run a task to generate code.</p>
          </div>
        )}
        {activePath && content === undefined && <p className="p-4 text-sm text-ide-muted">Loading...</p>}
        {activePath && content !== undefined && (
          <>
            <div className="sticky top-0 z-10 flex items-center justify-between px-4 py-1 text-[11px] bg-ide-panel/95 text-ide-muted border-b border-ide-border">
              <span className="font-mono truncate">{activePath}</span>
              <span className="flex-shrink-0 ml-3">read-only · {languageFor(activePath)} · {lines.length} lines</span>
            </div>
            <pre className="text-[13px] leading-5 font-mono py-2 m-0">
              {lines.map((line, index) => (
                <div key={index} className="flex hover:bg-ide-hover/40">
                  <span className="select-none text-right text-ide-faint w-12 pr-3 flex-shrink-0">{index + 1}</span>
                  <code className="whitespace-pre pr-6">
                    {line.length ? line.map((token, i) => <span key={i} className={COLORS[token.type]}>{token.text}</span>) : ' '}
                  </code>
                </div>
              ))}
            </pre>
          </>
        )}
      </div>
    </div>
  )
}

export default CodeEditor
