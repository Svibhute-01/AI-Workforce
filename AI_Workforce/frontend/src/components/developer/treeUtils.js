// Turns a flat list of file paths into a nested tree: folders first, then files, each sorted by name.
export function buildTree(paths) {
  const root = { name: '', path: '', type: 'folder', children: [] }

  for (const path of paths) {
    const parts = path.split('/').filter(Boolean)
    let node = root
    parts.forEach((part, index) => {
      const isFile = index === parts.length - 1
      const nodePath = parts.slice(0, index + 1).join('/')
      let child = node.children.find((item) => item.name === part && item.type === (isFile ? 'file' : 'folder'))
      if (!child) {
        child = isFile
          ? { name: part, path: nodePath, type: 'file' }
          : { name: part, path: nodePath, type: 'folder', children: [] }
        node.children.push(child)
      }
      node = child
    })
  }

  const sortNode = (node) => {
    if (!node.children) return
    node.children.sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === 'folder' ? -1 : 1))
    node.children.forEach(sortNode)
  }
  sortNode(root)
  return root.children
}
