import { useState } from 'react'
import { ChevronDown, ChevronRight, File, Folder } from 'lucide-react'

function Node({ node, depth, selectedPath, onSelect }) {
  const [open, setOpen] = useState(depth < 2)
  const indent = { paddingLeft: `${depth * 14 + 8}px` }

  if (node.type === 'file') {
    const active = node.path === selectedPath
    return (
      <button
        onClick={() => onSelect(node.path)}
        style={indent}
        className={`w-full flex items-center gap-2 py-1.5 pr-2 text-sm text-left rounded ${active ? 'bg-primary-light text-primary font-medium' : 'text-text-primary hover:bg-gray-50'}`}
        title={node.path}
      >
        <File className="w-4 h-4 flex-shrink-0 text-text-secondary" />
        <span className="truncate">{node.name}</span>
      </button>
    )
  }

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        style={indent}
        className="w-full flex items-center gap-2 py-1.5 pr-2 text-sm text-left text-text-primary hover:bg-gray-50 rounded"
      >
        {open ? <ChevronDown className="w-4 h-4 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 flex-shrink-0" />}
        <Folder className="w-4 h-4 flex-shrink-0 text-primary" />
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
    return <p className="text-sm text-text-secondary p-3">No files yet. Run a task and the generated code appears here.</p>
  }
  return (
    <div>
      {tree.map((node) => (
        <Node key={node.path + node.type} node={node} depth={0} selectedPath={selectedPath} onSelect={onSelect} />
      ))}
    </div>
  )
}

export default FileTree
