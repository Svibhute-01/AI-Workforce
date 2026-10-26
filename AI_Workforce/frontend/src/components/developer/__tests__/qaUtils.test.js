import test from 'node:test'
import assert from 'node:assert/strict'
import { canSendDefects, failedSteps, latestByTask, summaryLine, verdictInfo } from '../qaUtils.js'

test('every verdict has a label and a tone, unknown ones are shown as they are', () => {
  assert.deepEqual(verdictInfo('PASS'), { label: 'Pass', tone: 'success' })
  assert.equal(verdictInfo('FAIL').tone, 'danger')
  assert.equal(verdictInfo('UNVERIFIED').tone, 'warn')
  assert.equal(verdictInfo('BLOCKED').tone, 'danger')
  assert.deepEqual(verdictInfo('SOMETHING'), { label: 'SOMETHING', tone: 'muted' })
  assert.deepEqual(verdictInfo(null), { label: 'Pending', tone: 'muted' })
})

test('the newest run of each task wins, whatever order the runs arrive in', () => {
  const runs = [{ id: 1, task_id: 'T1' }, { id: 5, task_id: 'T1' }, { id: 3, task_id: 'T2' }, { id: 9 }]
  assert.deepEqual(Object.fromEntries(Object.entries(latestByTask(runs)).map(([k, v]) => [k, v.id])), { T1: 5, T2: 3 })
  assert.deepEqual(latestByTask([]), {})
})

test('the summary line tells the story in one sentence', () => {
  const run = { status: 'COMPLETED', verdict: 'FAIL', total: 3, coverage: 66.7, counts: { PASS: 1, FAIL: 1, UNVERIFIED: 1 } }
  assert.equal(summaryLine(run), 'FAIL · 1 of 3 criteria passed · 1 failed · 1 not verified · 66.7% verified')
  assert.equal(summaryLine({ status: 'COMPLETED', verdict: 'PASS', total: 2, coverage: 100, counts: { PASS: 2 } }),
    'PASS · 2 of 2 criteria passed · 100% verified')
  assert.equal(summaryLine({ status: 'PROCESSING' }), 'QA is testing the running app...')
  assert.equal(summaryLine(null), '')
})

test('only the steps that failed are returned, with their evidence', () => {
  const row = { scenarios: [{ steps: [{ request: 'POST /a', failures: [] }, { request: 'POST /b', failures: ['expected 409, got 201'] }] }] }
  assert.deepEqual(failedSteps(row).map((step) => step.request), ['POST /b'])
  assert.deepEqual(failedSteps({}), [])
})

test('defects can be sent once, and only for a finished run that failed', () => {
  assert.equal(canSendDefects({ status: 'COMPLETED', verdict: 'FAIL', defects_sent: false }), true)
  assert.equal(canSendDefects({ status: 'COMPLETED', verdict: 'FAIL', defects_sent: true }), false)
  assert.equal(canSendDefects({ status: 'COMPLETED', verdict: 'PASS' }), false)
  assert.equal(canSendDefects({ status: 'PROCESSING', verdict: 'FAIL' }), false)
  assert.equal(canSendDefects(null), false)
})
