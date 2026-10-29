import { useId } from 'react'

function BrandMark({ size = 40, className = '' }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={`bm-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#65DDF4" />
          <stop offset="0.5" stopColor="#536DFE" />
          <stop offset="1" stopColor="#3155D9" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="18" fill="#0B1E3B" />
      <rect width="64" height="64" rx="18" fill={`url(#bm-${id})`} opacity="0.92" />
      <ellipse cx="32" cy="32" rx="22" ry="9" fill="none" stroke="#FFFFFF" strokeOpacity="0.85" strokeWidth="2.2" transform="rotate(-24 32 32)" />
      <circle cx="32" cy="32" r="8" fill="#FFFFFF" />
      <circle cx="32" cy="32" r="3.2" fill="#3155D9" />
      <circle cx="49" cy="20" r="3" fill="#65DDF4" />
    </svg>
  )
}

export default BrandMark
