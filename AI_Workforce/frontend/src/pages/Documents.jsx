import { useEffect, useMemo, useState } from 'react'
import { Upload, Search } from 'lucide-react'
import apiService from '../services/api'

function Documents() {
  const [projects, setProjects] = useState([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [documentList, setDocumentList] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState('')

  const loadDocuments = async (projectId) => {
    if (!projectId) {
      setDocumentList([])
      return
    }
    try {
      setDocumentList(await apiService.documents.getForProject(projectId))
      setError('')
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  useEffect(() => {
    apiService.projects.getAll()
      .then((items) => {
        setProjects(items)
        if (items.length) setSelectedProjectId(String(items[0].id))
      })
      .catch((requestError) => setError(requestError.message))
  }, [])

  useEffect(() => {
    loadDocuments(selectedProjectId)
  }, [selectedProjectId])

  const filteredDocuments = useMemo(
    () => documentList.filter((doc) => doc.filename.toLowerCase().includes(searchTerm.toLowerCase())),
    [documentList, searchTerm]
  )

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || !selectedProjectId) {
      setError('Create or select a project before uploading an SRS.')
      return
    }
    setIsUploading(true)
    setError('')
    try {
      await apiService.documents.upload(file, selectedProjectId)
      await loadDocuments(selectedProjectId)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-2">Documents</h1>
          <p className="text-text-secondary">Upload and process an SRS for Requirements Analyst AI</p>
        </div>
        <label className={`btn-primary flex items-center gap-2 ${isUploading || !selectedProjectId ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}>
          <Upload className="w-5 h-5" />
          {isUploading ? 'Processing...' : 'Upload SRS PDF'}
          <input type="file" onChange={handleFileUpload} className="hidden" accept=".pdf,application/pdf" disabled={isUploading || !selectedProjectId} />
        </label>
      </div>

      {error && <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">{error}</div>}

      <div className="card p-6 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <label className="flex-1">
            <span className="block text-sm font-medium text-text-primary mb-2">Project</span>
            <select value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)} className="input-field w-full">
              {!projects.length && <option value="">No projects available</option>}
              {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          </label>
          <label className="flex-1">
            <span className="block text-sm font-medium text-text-primary mb-2">Search documents</span>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-secondary" />
              <input type="text" placeholder="Search by filename..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="input-field pl-10 w-full" />
            </div>
          </label>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr className="table-header">
              <th className="px-6 py-3 text-left">Document Name</th><th className="px-6 py-3 text-left">Type</th>
              <th className="px-6 py-3 text-left">Uploaded On</th><th className="px-6 py-3 text-left">Size</th><th className="px-6 py-3 text-left">Processing</th>
            </tr></thead>
            <tbody>
              {filteredDocuments.map((doc) => (
                <tr key={doc.id} className="border-b border-border-light hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 font-medium text-primary">{doc.filename}</td>
                  <td className="px-6 py-4 text-text-secondary text-sm">{doc.file_type}</td>
                  <td className="px-6 py-4 text-text-secondary text-sm">{doc.upload_time ? new Date(doc.upload_time).toLocaleDateString() : '—'}</td>
                  <td className="px-6 py-4 text-text-secondary text-sm">{(doc.file_size / (1024 * 1024)).toFixed(2)} MB</td>
                  <td className="px-6 py-4"><span className={`px-3 py-1 rounded-full text-xs font-medium ${doc.processing_status === 'COMPLETED' ? 'bg-green-100 text-green-800' : doc.processing_status === 'FAILED' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}`}>{doc.processing_status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filteredDocuments.length && <p className="p-8 text-center text-text-secondary">{selectedProjectId ? 'No SRS documents uploaded for this project.' : 'Create a project to upload an SRS.'}</p>}
        </div>
        <div className="p-6 border-t border-border-light"><p className="text-sm text-text-secondary">Showing {filteredDocuments.length} of {documentList.length} documents</p></div>
      </div>
    </div>
  )
}

export default Documents