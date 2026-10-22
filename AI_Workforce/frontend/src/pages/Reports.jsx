import { BarChart3, TrendingUp } from 'lucide-react'
import StatCard from '../components/common/StatCard'

function Reports() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">Reports & Analytics</h1>
        <p className="text-text-secondary">Insights and analytics about your projects</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Total Projects"
          value="12"
          change="+2 this month"
          icon={BarChart3}
          trend="up"
        />
        <StatCard
          title="Tasks Completed"
          value="156"
          change="+20% from last month"
          icon={TrendingUp}
          trend="up"
        />
        <StatCard
          title="Success Rate"
          value="87%"
          change="+5% improvement"
          icon={TrendingUp}
          trend="up"
        />
        <StatCard
          title="Avg. Completion"
          value="4.2 days"
          change="-0.8 days faster"
          icon={TrendingUp}
          trend="up"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="card p-6">
          <h2 className="text-lg font-bold text-text-primary mb-6">Task Status Distribution</h2>
          <div className="flex items-center justify-center min-h-64">
            <div className="text-center">
              <div className="relative w-48 h-48 mx-auto mb-6">
                <svg className="w-full h-full" viewBox="0 0 200 200">
                  <circle cx="100" cy="100" r="90" fill="none" stroke="#3b82f6" strokeWidth="20" 
                    strokeDasharray="188 565" strokeDashoffset="0" />
                  <circle cx="100" cy="100" r="90" fill="none" stroke="#10b981" strokeWidth="20" 
                    strokeDasharray="141 565" strokeDashoffset="-188" />
                  <circle cx="100" cy="100" r="90" fill="none" stroke="#f59e0b" strokeWidth="20" 
                    strokeDasharray="57 565" strokeDashoffset="-329" />
                  <text x="100" y="100" textAnchor="middle" dy="0.3em" className="text-2xl font-bold" fill="#1a1a1a">
                    348
                  </text>
                  <text x="100" y="120" textAnchor="middle" className="text-xs" fill="#666666">
                    Total Tasks
                  </text>
                </svg>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-center gap-2">
                  <div className="w-3 h-3 bg-blue-400 rounded-full"></div>
                  <span>In Progress: 186 (53%)</span>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  <span>Completed: 112 (32%)</span>
                </div>
                <div className="flex items-center justify-center gap-2">
                  <div className="w-3 h-3 bg-yellow-400 rounded-full"></div>
                  <span>Todo: 50 (15%)</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-bold text-text-primary mb-6">Project Progress Overview</h2>
          <div className="space-y-4">
            {[
              { name: 'E-Commerce Platform', progress: 75, color: '#5B2DD8' },
              { name: 'AI Chat Assistant', progress: 52, color: '#10b981' },
              { name: 'Inventory Management', progress: 30, color: '#f59e0b' },
              { name: 'HR Management', progress: 90, color: '#3b82f6' },
              { name: 'Bug Tracking System', progress: 100, color: '#6366f1' },
            ].map((project, index) => (
              <div key={index}>
                <div className="flex justify-between items-center mb-2">
                  <p className="font-medium text-text-primary text-sm">{project.name}</p>
                  <span className="text-sm font-semibold text-text-primary">{project.progress}%</span>
                </div>
                <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full transition-all"
                    style={{ width: `${project.progress}%`, backgroundColor: project.color }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-bold text-text-primary mb-6">Monthly Performance Trend</h2>
        <div className="h-64 flex items-end justify-around gap-2 px-4">
          {[
            { month: 'May', tasks: 65, color: '#5B2DD8' },
            { month: 'June', tasks: 85, color: '#5B2DD8' },
            { month: 'July', tasks: 78, color: '#5B2DD8' },
            { month: 'Aug', tasks: 95, color: '#5B2DD8' },
            { month: 'Sep', tasks: 110, color: '#5B2DD8' },
            { month: 'Oct', tasks: 105, color: '#5B2DD8' },
          ].map((item, index) => (
            <div key={index} className="flex-1 flex flex-col items-center gap-2">
              <div
                className="w-full rounded-t-lg transition-all hover:opacity-80"
                style={{
                  height: `${(item.tasks / 120) * 100}%`,
                  backgroundColor: item.color,
                }}
              ></div>
              <span className="text-xs text-text-secondary font-medium">{item.month}</span>
            </div>
          ))}
        </div>
        <a href="#" className="text-primary hover:text-primary-dark text-sm font-medium mt-6 inline-block">
          View detailed report
        </a>
      </div>
    </div>
  )
}

export default Reports
