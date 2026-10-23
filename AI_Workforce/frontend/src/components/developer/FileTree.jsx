import { useState } from 'react'
import { ChevronDown, ChevronRight, File, FileCode, Folder, FolderOpen } from 'lucide-react'

function Node({ node, depth, selectedPath, onSelect }) {
  const [open, setOpen] = useState(depth < 2)
  const indent = { paddingLeft: `${depth * 12 + 8}px` }

  if (node.type === 'file') {
    const active = node.path === selectedPath
    const Icon = node.name.endsWith('.py') ? FileCode : File
    return (
      <button
        onClick={() => onSelect(node.path)}
        style={indent}
        title={node.path}
        className={`w-full flex items-center gap-2 py-1 pr-2 text-[13px] text-left ${active ? 'bg-ide-accent/20 text-ide-text' : 'text-ide-text2 hover:bg-ide-hover'}`}
      >
        <Icon className={`w-4 h-4 flex-shrink-0 ${node.name.endsWith('.py') ? 'text-ide-info' : 'text-ide-muted'}`} />
        <span className="truncate">{node.name}</span>
      </button>
    )
  }

  const FolderIcon = open ? FolderOpen : Folder
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        style={indent}
        className="w-full flex items-center gap-1.5 py-1 pr-2 text-[13px] text-left text-ide-text hover:bg-ide-hover"
      >
        {open ? <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 text-ide-muted" /> : <ChevronRight className="w-3.5 h-3.5 flex-shrink-0 text-ide-muted" />}
        <FolderIcon className="w-4 h-4 flex-shrink-0 text-ide-warn" />
        <span className="truncate">{node.name}</span>
      </button>
      {open && node.children.map((child) => (
        <Node key={child.path + child.type} node={child} depth={depth + 1} selectedPath={selectedPath} onSelect={onSelect} />
      ))}
    </div>
  )
}

function FileTree({ tree, selectedPath, onSelect }) {
  if (!tree.length) {
    return <p className="text-[13px] text-ide-muted p-3">No files yet. Press Run on a task and the generated code appears here.</p>
  }
  return (
    <div className="py-1">
      {tree.map((node) => (
        <Node key={node.path + node.type} node={node} depth={0} selectedPath={selectedPath} onSelect={onSelect} />
      ))}
    </div>
  )
}

export default FileTree
