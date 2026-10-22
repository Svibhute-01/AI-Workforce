import { useState } from 'react'
import { Plus, Search, Filter } from 'lucide-react'
import Modal from '../components/common/Modal'
import StatusBadge from '../components/common/StatusBadge'
import { tasks as initialTasks } from '../data/tasks'

function Tasks() {
  const [taskList, setTaskList] = useState(initialTasks)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterProject, setFilterProject] = useState('All Projects')
  const [filterStatus, setFilterStatus] = useState('All Status')
  const [formData, setFormData] = useState({
    name: '',
    project: '',
    assignee: '',
    priority: 'Medium',
    status: 'Todo',
    dueDate: '',
  })

  const uniqueProjects = ['All Projects', ...new Set(taskList.map(t => t.project))]
  const uniqueStatuses = ['All Status', 'Todo', 'In Progress', 'Completed']

  const filteredTasks = taskList.filter(task => {
    const matchesSearch = task.name.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesProject = filterProject === 'All Projects' || task.project === filterProject
    const matchesStatus = filterStatus === 'All Status' || task.status === filterStatus
    return matchesSearch && matchesProject && matchesStatus
  })

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'High':
        return 'text-red-600'
      case 'Medium':
        return 'text-orange-600'
      case 'Low':
        return 'text-green-600'
      default:
        return 'text-text-secondary'
    }
  }

  const handleCreateTask = () => {
    if (formData.name && formData.project && formData.assignee) {
      const newTask = {
        id: taskList.length + 1,
        ...formData,
      }
      setTaskList([...taskList, newTask])
      setFormData({
        name: '',
        project: '',
        assignee: '',
        priority: 'Medium',
        status: 'Todo',
        dueDate: '',
      })
      setIsModalOpen(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-text-primary mb-2">Tasks</h1>
          <p className="text-text-secondary">Organize and track your tasks</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          New Task
        </button>
      </div>

      <div className="card p-6 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-secondary" />
            <input
              type="text"
              placeholder="Search tasks..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input-field pl-10 w-full"
            />
          </div>

          <select
            value={filterProject}
            onChange={(e) => setFilterProject(e.target.value)}
            className="input-field"
          >
            {uniqueProjects.map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="input-field"
          >
            {uniqueStatuses.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="table-header">
                <th className="px-6 py-3 text-left">Task</th>
                <th className="px-6 py-3 text-left">Project</th>
                <th className="px-6 py-3 text-left">Assignee</th>
                <th className="px-6 py-3 text-left">Priority</th>
                <th className="px-6 py-3 text-left">Status</th>
                <th className="px-6 py-3 text-left">Due Date</th>
              </tr>
            </thead>
            <tbody>
              {filteredTasks.map((task) => (
                <tr key={task.id} className="border-b border-border-light hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 font-medium text-text-primary">{task.name}</td>
                  <td className="px-6 py-4 text-text-secondary text-sm">{task.project}</td>
                  <td className="px-6 py-4 text-text-primary text-sm">{task.assignee}</td>
                  <td className="px-6 py-4">
                    <span className={`text-sm font-medium ${getPriorityColor(task.priority)}`}>
                      {task.priority}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={task.status} />
                  </td>
                  <td className="px-6 py-4 text-text-secondary text-sm">{task.dueDate}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between p-6 border-t border-border-light">
          <p className="text-sm text-text-secondary">Showing 1 to {filteredTasks.length} of {taskList.length} tasks</p>
          <div className="flex gap-2">
            <button className="px-3 py-1 border border-border-light rounded-lg text-text-secondary hover:bg-gray-50">1</button>
            <button className="px-3 py-1 border border-border-light rounded-lg text-text-secondary hover:bg-gray-50">2</button>
            <button className="px-3 py-1 border border-border-light rounded-lg text-text-secondary hover:bg-gray-50">3</button>
          </div>
        </div>
      </div>

      <Modal
        isOpen={isModalOpen}
        title="Create New Task"
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleCreateTask}
        submitText="Create Task"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Task Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="input-field w-full"
              placeholder="Enter task name"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Project</label>
            <select
              value={formData.project}
              onChange={(e) => setFormData({ ...formData, project: e.target.value })}
              className="input-field w-full"
            >
              <option value="">Select a project</option>
              {uniqueProjects.filter(p => p !== 'All Projects').map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Assignee</label>
            <input
              type="text"
              value={formData.assignee}
              onChange={(e) => setFormData({ ...formData, assignee: e.target.value })}
              className="input-field w-full"
              placeholder="Enter assignee name"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Priority</label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                className="input-field w-full"
              >
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text-primary mb-1">Status</label>
              <select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                className="input-field w-full"
              >
                <option>Todo</option>
                <option>In Progress</option>
                <option>Completed</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1">Due Date</label>
            <input
              type="date"
              value={formData.dueDate}
              onChange={(e) => setFormData({ ...formData, dueDate: e.target.value })}
              className="input-field w-full"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default Tasks
