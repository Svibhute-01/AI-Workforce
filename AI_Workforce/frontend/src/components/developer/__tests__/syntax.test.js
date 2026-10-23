import test from 'node:test'
import assert from 'node:assert/strict'
import { highlight, languageFor } from '../syntax.js'

const typesOf = (line) => line.filter((token) => token.type !== 'plain').map((token) => `${token.type}:${token.text}`)

test('finds keywords, names, strings, numbers and comments in Python', () => {
  const [line] = highlight('def add(a, b): return "x" + 42  # sum', 'python')
  assert.deepEqual(typesOf(line), ['keyword:def', 'name:add', 'keyword:return', 'string:"x"', 'number:42', 'comment:# sum'])
})

test('marks decorators and class names', () => {
  const lines = highlight('@app.get("/")\nclass User:\n    pass', 'python')
  assert.deepEqual(typesOf(lines[0]), ['decorator:@app.get', 'string:"/"'])
  assert.deepEqual(typesOf(lines[1]), ['keyword:class', 'name:User'])
})

test('a docstring spanning lines stays a string on every line', () => {
  const lines = highlight('"""one\ntwo"""\nx = 1', 'python')
  assert.equal(lines.length, 3)
  assert.deepEqual(typesOf(lines[0]), ['string:"""one'])
  assert.deepEqual(typesOf(lines[1]), ['string:two"""'])
  assert.deepEqual(typesOf(lines[2]), ['number:1'])
})

test('words that merely contain a keyword are not keywords', () => {
  const [line] = highlight('classify = important', 'python')
  assert.deepEqual(typesOf(line), [])
})

test('a hash inside a string is not a comment', () => {
  const [line] = highlight('color = "#fff"', 'python')
  assert.deepEqual(typesOf(line), ['string:"#fff"'])
})

test('prefixed strings are strings', () => {
  const [line] = highlight("f'{x}'", 'python')
  assert.deepEqual(typesOf(line), ["string:f'{x}'"])
})

test('JSON separates keys from string values', () => {
  const [line] = highlight('{"name": "app", "n": 3, "ok": true}', 'json')
  assert.deepEqual(typesOf(line), ['name:"name"', 'string:"app"', 'name:"n"', 'number:3', 'name:"ok"', 'keyword:true'])
})

test('plain text and very large files are not tokenized', () => {
  assert.deepEqual(highlight('def x', 'text')[0], [{ text: 'def x', type: 'plain' }])
  const big = 'def x\n'.repeat(30000)
  assert.ok(highlight(big, 'python').every((line) => line.every((token) => token.type === 'plain')))
})

test('keeps blank lines and rebuilds the original text', () => {
  const code = 'a = 1\n\n# end\n'
  const lines = highlight(code, 'python')
  assert.equal(lines.map((line) => line.map((token) => token.text).join('')).join('\n'), code)
})

test('picks the language from the file name', () => {
  assert.equal(languageFor('app/main.py'), 'python')
  assert.equal(languageFor('package.json'), 'json')
  assert.equal(languageFor('requirements.txt'), 'text')
})
