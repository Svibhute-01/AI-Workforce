function ProgressBar({ progress, showLabel = true, size = 'md', tone = 'default' }) {
  const value = Math.max(0, Math.min(100, Number(progress) || 0))
  const heightClass = { sm: 'h-2', md: 'h-2.5', lg: 'h-3.5' }[size]
  const toneClass = tone === 'alert' ? 'alert' : tone === 'leaf' ? 'leaf' : tone === 'cool' ? 'cool' : ''

  return (
    <div className="flex items-center gap-3">
      <div className={`bt-track flex-1 ${heightClass}`} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}>
        <div className={`bt-fill ${toneClass}`} style={{ width: `${value}%` }}></div>
      </div>
      {showLabel && <span className="min-w-max text-xs font-bold tabular-nums text-text-primary">{value}%</span>}
    </div>
  )
}

export default ProgressBar
