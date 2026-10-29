import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Folder, Plus, RefreshCw, Search } from 'lucide-react'
import Modal from '../components/common/Modal'
import StatusBadge from '../components/common/StatusBadge'
import ProgressBar from '../components/common/ProgressBar'
import { EmptyState, ErrorState, Notice, PageHeader, Skeleton } from '../components/common/States'
import apiService from '../services/api'

const BLANK_FORM = { name: '', description: '', manager: '', startDate: '', dueDate: '', status: 'Planning' }

function Projects() {
  const [projectList, setProjectList] = useState([])
  const [loading, setLoading] = useState(true)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [success, setSuccess] = useState('')
  const [formData, setFormData] = useState(BLANK_FORM)
  const alive = useRef(true)

  const loadProjects = useCallback(async () => {
    try {
      const items = await apiService.projects.getAll()
      if (!alive.current) return
      setProjectList(items)
      setError('')
    } catch (requestError) {
      if (alive.current) setError(requestError.message)
    } finally {
      if (alive.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    alive.current = true
    loadProjects()
    return () => { alive.current = false }
  }, [loadProjects])

  const statuses = useMemo(() => [...new Set(projectList.map((project) => project.status).filter(Boolean))], [projectList])

  const filteredProjects = projectList.filter((project) =>
    project.name.toLowerCase().includes(searchTerm.toLowerCase()) &&
    (statusFilter === 'all' || project.status === statusFilter)
  )

  const closeModal = useCallback(() => {
    setIsModalOpen(false)
    setFormError('')
  }, [])

  const handleCreateProject = async () => {
    if (!formData.name.trim()) {
      setFormError('Project name is required.')
      return
    }
    setSaving(true)
    setFormError('')
    try {
      await apiService.projects.create({
        name: formData.name,
        description: formData.description || null,
        manager: formData.manager || null,
        start_date: formData.startDate || null,
        due_date: formData.dueDate || null,
        status: formData.status,
      })
      setSuccess(`Project "${formData.name}" was created.`)
      setFormData(BLANK_FORM)
      setIsModalOpen(false)
      await loadProjects()
    } catch (requestError) {
      setFormError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Projects"
        subtitle="Manage and track all your projects"
        actions={(
          <>
            <button type="button" onClick={() => { setLoading(true); loadProjects() }} disabled={loading} className="btn-outline flex items-center gap-2">
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </button>
            <button onClick={() => setIsModalOpen(true)} className="btn-primary flex items-center gap-2">
              <Plus className="h-5 w-5" /> New Project
            </button>
          </>
        )}
      />

      {success && <Notice tone="success" onDismiss={() => setSuccess('')}>{success}</Notice>}
      {error && projectList.length > 0 && <Notice tone="error" onRetry={loadProjects}>{error}</Notice>}

      {loading && !projectList.length ? (
        <div className="space-y-4" aria-busy="true" aria-label="Loading projects">
          <Skeleton className="h-20" />
          <Skeleton className="h-80" />
        </div>
      ) : error && !projectList.length ? (
        <ErrorState title="Couldn't load projects" message={error} onRetry={() => { setLoading(true); loadProjects() }} retrying={loading} />
      ) : (
        <>
          <div className="card mb-6 p-5">
            <div className="flex flex-col gap-4 md:flex-row">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                <input type="search" aria-label="Search projects" placeholder="Search projects..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="input-field w-full pl-10" />
              </div>
              <select aria-label="Filter by status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input-field md:w-52">
                <option value="all">All statuses</option>
                {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px]">
                <thead><tr className="table-header">
                  <th className="px-6 py-3 text-left">Project Name</th><th className="px-6 py-3 text-left">Manager</th>
                  <th className="px-6 py-3 text-left">Progress</th><th className="px-6 py-3 text-left">Status</th>
                  <th className="px-6 py-3 text-left">Created On</th>
                </tr></thead>
                <tbody>
                  {filteredProjects.map((project) => (
                    <tr key={project.id} className="border-b border-border-light last:border-b-0">
                      <td className="px-6 py-4"><Link to={`/projects/${project.id}`} className="flex items-center gap-2 font-bold text-primary hover:underline"><Folder className="h-4 w-4 shrink-0" />{project.name}</Link></td>
                      <td className="px-6 py-4 text-text-primary">{project.manager || '—'}</td>
                      <td className="px-6 py-4"><div className="w-36"><ProgressBar progress={project.progress || 0} showLabel size="sm" /></div></td>
                      <td className="px-6 py-4"><StatusBadge status={project.status} /></td>
                      <td className="px-6 py-4 text-sm text-text-secondary">{project.created_at ? new Date(project.created_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!filteredProjects.length && (
                projectList.length ? (
                  <p className="p-8 text-center text-text-secondary">No projects match your search or filter.</p>
                ) : (
                  <div className="p-6"><EmptyState icon={Folder} title="No projects yet" hint="Create your first project to upload an SRS and start the AI workflow." /></div>
                )
              )}
            </div>
            <div className="border-t border-border-light p-5"><p className="text-sm text-text-secondary">Showing {filteredProjects.length} of {projectList.length} projects</p></div>
          </div>
        </>
      )}

      <Modal isOpen={isModalOpen} title="Create New Project" onClose={closeModal} onSubmit={handleCreateProject} submitText="Create Project" submitting={saving}>
        <div className="space-y-4">
          {formError && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{formError}</p>}
          <div><label htmlFor="pname" className="mb-1 block text-sm font-semibold text-text-primary">Project Name</label><input id="pname" type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="input-field w-full" placeholder="Enter project name" /></div>
          <div><label htmlFor="pdesc" className="mb-1 block text-sm font-semibold text-text-primary">Description</label><textarea id="pdesc" value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} className="input-field w-full" rows="3" placeholder="Describe the project scope" /></div>
          <div><label htmlFor="pmgr" className="mb-1 block text-sm font-semibold text-text-primary">Manager</label><input id="pmgr" type="text" value={formData.manager} onChange={(e) => setFormData({ ...formData, manager: e.target.value })} className="input-field w-full" placeholder="Enter manager name" /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label htmlFor="pstart" className="mb-1 block text-sm font-semibold text-text-primary">Start Date</label><input id="pstart" type="date" value={formData.startDate} onChange={(e) => setFormData({ ...formData, startDate: e.target.value })} className="input-field w-full" /></div>
            <div><label htmlFor="pdue" className="mb-1 block text-sm font-semibold text-text-primary">Due Date</label><input id="pdue" type="date" value={formData.dueDate} onChange={(e) => setFormData({ ...formData, dueDate: e.target.value })} className="input-field w-full" /></div>
          </div>
          <div><label htmlFor="pstat" className="mb-1 block text-sm font-semibold text-text-primary">Status</label><select id="pstat" value={formData.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })} className="input-field w-full"><option>Planning</option><option>In Progress</option><option>Completed</option></select></div>
        </div>
      </Modal>
    </div>
  )
}

export default Projects
