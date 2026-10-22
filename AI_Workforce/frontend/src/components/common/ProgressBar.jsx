function ProgressBar({ progress, showLabel = true, size = 'md' }) {
  const heightClass = {
    sm: 'h-2',
    md: 'h-3',
    lg: 'h-4',
  }[size]

  return (
    <div className="flex items-center gap-3">
      <div className={`flex-1 bg-gray-200 rounded-full overflow-hidden ${heightClass}`}>
        <div
          className="bg-primary h-full rounded-full transition-all duration-300"
          style={{ width: `${progress}%` }}
        ></div>
      </div>
      {showLabel && <span className="text-sm font-medium text-text-primary min-w-max">{progress}%</span>}
    </div>
  )
}

export default ProgressBar
