import { TrendingUp, TrendingDown } from 'lucide-react'

function StatCard({ title, value, change, icon: Icon, trend = 'up' }) {
  const isPositive = trend === 'up'
  const trendColor = isPositive ? 'text-green-600' : 'text-red-600'
  const bgColor = isPositive ? 'bg-green-50' : 'bg-red-50'

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-text-secondary text-sm mb-2">{title}</p>
          <p className="text-3xl font-bold text-text-primary">{value}</p>
          <p className={`text-sm mt-2 flex items-center gap-1 ${trendColor}`}>
            {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            {change}
          </p>
        </div>
        {Icon && (
          <div className="bg-primary-light p-3 rounded-lg">
            <Icon className="w-6 h-6 text-primary" />
          </div>
        )}
      </div>
    </div>
  )
}

export default StatCard
