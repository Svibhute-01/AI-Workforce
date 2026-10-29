import { TrendingDown, TrendingUp } from 'lucide-react'

function StatCard({ title, value, change, icon: Icon, trend = 'none' }) {
  const trendColor = trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-700' : 'text-text-secondary'
  const TrendIcon = trend === 'down' ? TrendingDown : TrendingUp

  return (
    <div className="card lift group p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-text-secondary">{title}</p>
          <p className="text-3xl font-extrabold tabular-nums text-text-primary">{value}</p>
          {change && (
            <p className={`mt-2 flex items-center gap-1 text-sm ${trendColor}`}>
              {trend !== 'none' && <TrendIcon className="h-4 w-4" />}
              {change}
            </p>
          )}
        </div>
        {Icon && (
          <div className="bt-icon-bubble h-11 w-11 shrink-0">
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>
    </div>
  )
}

export default StatCard
