import test from 'node:test'
import assert from 'node:assert/strict'
import { buildTree } from '../treeUtils.js'

test('groups paths into folders, with folders listed before files', () => {
  const tree = buildTree(['requirements.txt', 'app/main.py', 'app/routes/auth.py', 'app/__init__.py'])

  assert.deepEqual(tree.map((node) => node.name), ['app', 'requirements.txt'])
  const app = tree[0]
  assert.deepEqual(app.children.map((node) => `${node.type}:${node.name}`), [
    'folder:routes',
    'file:__init__.py',
    'file:main.py',
  ])
  assert.equal(app.children[0].children[0].path, 'app/routes/auth.py')
})

test('an empty workspace gives an empty tree', () => {
  assert.deepEqual(buildTree([]), [])
})

test('a file and a folder with the same name do not collide', () => {
  const tree = buildTree(['a', 'a/b.py'])
  assert.equal(tree.length, 2)
})
