import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = fileURLToPath(new URL('../../../../', import.meta.url))
const css = fs.readFileSync(path.join(root, 'src/index.css'), 'utf8')
const sources = [
  'src/pages/Developer.jsx',
  ...fs.readdirSync(path.join(root, 'src/components/developer')).filter((name) => name.endsWith('.jsx')).map((name) => `src/components/developer/${name}`),
].map((file) => ({ file, text: fs.readFileSync(path.join(root, file), 'utf8') }))

const variablesIn = (block) => [...block.matchAll(/--ide-([a-z0-9-]+):/g)].map((match) => match[1]).sort()
const blockAfter = (selector) => {
  const start = css.indexOf(selector)
  assert.notEqual(start, -1, `${selector} is missing from index.css`)
  return css.slice(start, css.indexOf('}', start))
}

test('light and dark themes define exactly the same palette', () => {
  const light = variablesIn(blockAfter('\n.ide {'))
  const dark = variablesIn(blockAfter("html[data-theme='dark'] .ide {"))
  assert.ok(light.length > 10)
  assert.deepEqual(light, dark)
})

test('every ide-* colour used by the workspace exists in Tailwind and in both themes', async () => {
  const config = (await import(pathToFileURL(path.join(root, 'tailwind.config.js')))).default
  const tailwindNames = Object.keys(config.theme.extend.colors.ide).sort()
  const themeNames = variablesIn(blockAfter('\n.ide {'))
  assert.deepEqual(tailwindNames, themeNames)

  for (const { file, text } of sources) {
    for (const match of text.matchAll(/-ide-([a-z0-9]+(?:-[a-z0-9]+)*)/g)) {
      assert.ok(themeNames.includes(match[1]), `${file} uses unknown colour ide-${match[1]}`)
    }
  }
})

test('the workspace has no hard-coded colours that would ignore the theme', () => {
  for (const { file, text } of sources) {
    assert.doesNotMatch(text, /-\[#[0-9a-fA-F]{3,8}\]/, `${file} has a hard-coded hex colour`)
  }
})

test('the workspace root opts into the palette', () => {
  const page = sources.find((source) => source.file === 'src/pages/Developer.jsx').text
  assert.match(page, /className="ide /)
})
