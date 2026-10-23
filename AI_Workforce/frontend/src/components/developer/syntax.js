// A small syntax highlighter (Python and JSON) so the editor needs no extra dependency.
// highlight(code, language) returns one array of { text, type } tokens per line.

const PY_KEYWORDS = new Set([
  'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
  'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if', 'import', 'in',
  'is', 'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
])

const PY_PATTERN = new RegExp(
  [
    String.raw`("""[\s\S]*?(?:"""|$)|'''[\s\S]*?(?:'''|$))`, // 1 triple-quoted string
    String.raw`(#[^\n]*)`, // 2 comment
    String.raw`((?:[rRbBfFuU]{1,2})?(?:"(?:\\.|[^"\\\n])*"?|'(?:\\.|[^'\\\n])*'?))`, // 3 string
    String.raw`(@[A-Za-z_][\w.]*)`, // 4 decorator
    String.raw`(\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b)`, // 5 number
    String.raw`([A-Za-z_]\w*)`, // 6 word
  ].join('|'),
  'g',
)

const JSON_PATTERN = /("(?:\\.|[^"\\\n])*")(\s*:)?|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|\b(true|false|null)\b/g

const MAX_HIGHLIGHT_CHARS = 100000

export function languageFor(path = '') {
  if (path.endsWith('.py')) return 'python'
  if (path.endsWith('.json')) return 'json'
  return 'text'
}

function tokenizePython(code) {
  const tokens = []
  let last = 0
  let previousWord = ''
  PY_PATTERN.lastIndex = 0

  for (let match = PY_PATTERN.exec(code); match; match = PY_PATTERN.exec(code)) {
    if (match.index > last) tokens.push({ text: code.slice(last, match.index), type: 'plain' })
    const [text, triple, comment, string, decorator, number, word] = match
    let type = 'plain'
    if (triple || string) type = 'string'
    else if (comment) type = 'comment'
    else if (decorator) type = 'decorator'
    else if (number) type = 'number'
    else if (word) {
      if (PY_KEYWORDS.has(word)) type = 'keyword'
      else if (previousWord === 'def' || previousWord === 'class') type = 'name'
    }
    tokens.push({ text, type })
    previousWord = word || ''
    last = match.index + text.length
    if (text.length === 0) PY_PATTERN.lastIndex += 1 // never loop on an empty match
  }
  if (last < code.length) tokens.push({ text: code.slice(last), type: 'plain' })
  return tokens
}

function tokenizeJson(code) {
  const tokens = []
  let last = 0
  JSON_PATTERN.lastIndex = 0
  for (let match = JSON_PATTERN.exec(code); match; match = JSON_PATTERN.exec(code)) {
    if (match.index > last) tokens.push({ text: code.slice(last, match.index), type: 'plain' })
    const [text, string, colon, number] = match
    if (string) {
      tokens.push({ text: string, type: colon ? 'name' : 'string' })
      if (colon) tokens.push({ text: colon, type: 'plain' })
    } else {
      tokens.push({ text, type: number ? 'number' : 'keyword' })
    }
    last = match.index + text.length
  }
  if (last < code.length) tokens.push({ text: code.slice(last), type: 'plain' })
  return tokens
}

// Tokens can span several lines (docstrings), so split them after tokenizing.
function toLines(tokens) {
  const lines = [[]]
  for (const token of tokens) {
    token.text.split('\n').forEach((piece, index) => {
      if (index > 0) lines.push([])
      if (piece) lines[lines.length - 1].push({ text: piece, type: token.type })
    })
  }
  return lines
}

export function highlight(code, language) {
  if (code.length > MAX_HIGHLIGHT_CHARS || language === 'text') return toLines([{ text: code, type: 'plain' }])
  return toLines(language === 'json' ? tokenizeJson(code) : tokenizePython(code))
}
