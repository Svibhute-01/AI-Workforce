import test from 'node:test'
import assert from 'node:assert/strict'
import { fmtBytes, pct, humanize, timeAgo } from '../format.js'
import { buildReport, reportToCsv } from '../reportModel.js'
import { flattenTasks, filterTasks, paginate } from '../taskModel.js'
import { buildActivity } from '../activityModel.js'
import { normalizeAnswer } from '../chatModel.js'

test('format helpers', () => {
  assert.equal(fmtBytes(2048), '2.0 KB')
  assert.equal(pct(1, 4), 25)
  assert.equal(pct(1, 0), 0)
  assert.equal(humanize('IN_PROGRESS'), 'In Progress')
  assert.equal(timeAgo(null), 'Never')
})

test('buildReport derives figures only from the summary', () => {
  assert.equal(buildReport(null), null)
  const report = buildReport({
    projects: { total: 2 },
    tasks: { total: 4, completed: 1, by_status: [{ key: 'TODO', count: 3 }, { key: 'COMPLETED', count: 1 }] },
    agents: [{ total_runs: 3, failed: 1 }, { total_runs: 2, failed: 0 }],
    project_overview: [{ id: 1, name: 'A, "B"', progress: 25 }],
  })
  assert.equal(report.totals.agentRuns, 5)
  assert.equal(report.totals.agentFailed, 1)
  assert.equal(report.statusRows[0].share, 75)
  assert.ok(reportToCsv(report).includes('"A, ""B"""'))
})

test('task flattening, filtering and paging', () => {
  const rows = flattenTasks([{ id: 1, name: 'P' }, { id: 2, name: 'Q' }], [
    { tasks: [{ id: 1, task_id: 'T1', title: 'Login', status: 'TODO', priority: 'HIGH', story_points: 3, sprint: 's1' }], sprints: [{ sprint_id: 's1', name: 'Sprint 1' }] },
    null,
  ])
  assert.equal(rows.length, 1)
  assert.equal(rows[0].sprint, 'Sprint 1')
  assert.equal(filterTasks(rows, { search: 'log' }).length, 1)
  assert.equal(filterTasks(rows, { status: 'COMPLETED' }).length, 0)
  assert.equal(paginate(rows, 5, 10).page, 1)
})

test('activity timeline is newest first', () => {
  const events = buildActivity({ id: 1, name: 'P', created_at: '2026-01-01T00:00:00Z' }, [{ id: 1, filename: 'a.pdf', upload_time: '2026-01-02T00:00:00Z' }], [{ id: 1, agent_name: 'X', status: 'COMPLETED', completed_at: '2026-01-03T00:00:00Z' }])
  assert.deepEqual(events.map((e) => e.kind), ['run', 'document', 'project'])
})

test('chat answers are normalised defensively', () => {
  assert.deepEqual(normalizeAnswer({ answer: ' hi ', sources: [{ document: 'srs.pdf', page: 2 }, 'x'] }), { text: 'hi', sources: ['srs.pdf · p.2', 'x'] })
  assert.equal(normalizeAnswer({ foo: 1 }).text, null)
})
