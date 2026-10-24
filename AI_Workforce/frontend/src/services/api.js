const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {})
  const token = localStorage.getItem('accessToken')

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  let payload = null

  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (!response.ok) {
    throw new Error(
      payload?.detail || `Request failed (${response.status})`
    )
  }

  return payload
}

export const apiService = {
  auth: {
    login: (data) =>
      request('/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    register: (data) =>
      request('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    me: () => request('/auth/me'),
  },

  projects: {
    getAll: () => request('/projects'),

    getById: (id) =>
      request(`/projects/${id}`),

    create: (data) =>
      request('/projects', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  documents: {
    getForProject: (projectId) =>
      request(`/projects/${projectId}/documents`),

    upload: (file, projectId) => {
      const formData = new FormData()
      formData.append('file', file)

      return request(`/projects/${projectId}/documents`, {
        method: 'POST',
        body: formData,
      })
    },
  },

  requirements: {
    analyze: (projectId) =>
      request(`/projects/${projectId}/analyze`, {
        method: 'POST',
      }),

    getAnalysis: (projectId) =>
      request(`/projects/${projectId}/analysis`),

    getRuns: (projectId) =>
      request(`/projects/${projectId}/agent-runs`),

    getRequirements: (projectId) =>
      request(`/projects/${projectId}/requirements`),

    getUserStories: (projectId) =>
      request(`/projects/${projectId}/user-stories`),

    getAcceptanceCriteria: (projectId) =>
      request(`/projects/${projectId}/acceptance-criteria`),
  },

  projectManager: {
    run: (projectId) =>
      request(`/projects/${projectId}/project-manager/run`, {
        method: 'POST',
      }),

    get: (projectId) =>
      request(`/projects/${projectId}/project-manager`),

    getTasks: (projectId) =>
      request(`/projects/${projectId}/tasks`),

    getSprints: (projectId) =>
      request(`/projects/${projectId}/sprints`),

    getMilestones: (projectId) =>
      request(`/projects/${projectId}/milestones`),

    getRisks: (projectId) =>
      request(`/projects/${projectId}/risks`),

    getDependencies: (projectId) =>
      request(`/projects/${projectId}/dependencies`),
  },

  architect: {
    run: (projectId) =>
      request(`/projects/${projectId}/architect/run`, {
        method: 'POST',
      }),

    get: (projectId) =>
      request(`/projects/${projectId}/architecture`),
  },

  developer: {
    listFiles: (projectId) =>
      request(`/projects/${projectId}/developer/workspace/files`),

    readFile: (projectId, path) =>
      request(`/projects/${projectId}/developer/workspace/file?path=${encodeURIComponent(path)}`),

    runTask: (projectId, taskId, force = false, stack = null) =>
      request(`/projects/${projectId}/developer/tasks/${encodeURIComponent(taskId)}/run`, {
        method: 'POST',
        body: JSON.stringify({ force, stack }),
      }),

    getStack: (projectId) =>
      request(`/projects/${projectId}/developer/stack`),

    getApp: (projectId) =>
      request(`/projects/${projectId}/developer/app`),

    startApp: (projectId) =>
      request(`/projects/${projectId}/developer/app/start`, { method: 'POST' }),

    stopApp: (projectId) =>
      request(`/projects/${projectId}/developer/app/stop`, { method: 'POST' }),

    getRuns: (projectId) =>
      request(`/projects/${projectId}/developer/runs`),

    getRun: (projectId, runId) =>
      request(`/projects/${projectId}/developer/runs/${runId}`),

    // Downloads a CSV of every run. It bypasses request() because the reply is a file, not JSON.
    exportRuns: async (projectId) => {
      const token = localStorage.getItem('accessToken')
      const response = await fetch(`${API_BASE_URL}/projects/${projectId}/developer/runs/export`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) {
        let detail = null
        try { detail = (await response.json()).detail } catch { /* not JSON */ }
        throw new Error(detail || `Export failed (${response.status})`)
      }
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = `developer-runs-project-${projectId}.csv`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    },

    runCommand: (projectId, command) =>
      request(`/projects/${projectId}/developer/commands`, {
        method: 'POST',
        body: JSON.stringify({ command }),
      }),
  },

  // Dashboard API
  dashboard: {
    getSummary: () =>
      request('/dashboard/summary'),
  },

  // Settings API
  settings: {
    getProfile: () =>
      request('/settings/profile'),

    updateProfile: (data) =>
      request('/settings/profile', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    changePassword: (data) =>
      request('/settings/password', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    getPreferences: () =>
      request('/settings/preferences'),

    updatePreferences: (data) =>
      request('/settings/preferences', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),

    getAI: () =>
      request('/settings/ai'),

    getSecurity: () =>
      request('/settings/security'),

    getIntegrations: () =>
      request('/settings/integrations'),
  },

  rag: {
    query: (projectId, query) =>
      request(`/projects/${projectId}/rag/query`, {
        method: 'POST',
        body: JSON.stringify({ query }),
      }),
  },
}

export default apiService