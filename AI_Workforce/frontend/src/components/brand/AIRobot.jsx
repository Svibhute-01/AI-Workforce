import { useId } from 'react'
import './ai-scene.css'

export function AIRobot({ mode = 'idle', className = '' }) {
  const id = useId().replace(/:/g, '')
  const closed = mode === 'password'
  const alert = mode === 'error'
  return (
    <div className={`ai-robot ${className}`} data-mode={mode}>
      <svg viewBox="0 0 400 470" className="ai-robot-svg" role="img" aria-label="AI Workforce assistant robot">
        <defs>
          <linearGradient id={`rb-body-${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#FFFFFF" />
            <stop offset="0.55" stopColor="#E6EDF8" />
            <stop offset="1" stopColor="#B9C9E2" />
          </linearGradient>
          <linearGradient id={`rb-head-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#FFFFFF" />
            <stop offset="1" stopColor="#D5E1F3" />
          </linearGradient>
          <linearGradient id={`rb-visor-${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#102A4C" />
            <stop offset="1" stopColor="#07152E" />
          </linearGradient>
          <radialGradient id={`rb-eye-${id}`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#FFFFFF" />
            <stop offset="0.35" stopColor="#65DDF4" />
            <stop offset="1" stopColor="#536DFE" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={`rb-chest-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#3155D9" />
            <stop offset="1" stopColor="#536DFE" />
          </linearGradient>
          <linearGradient id={`rb-metal-${id}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#9FB3D4" />
            <stop offset="0.5" stopColor="#F2F6FC" />
            <stop offset="1" stopColor="#8DA2C7" />
          </linearGradient>
          <radialGradient id={`rb-shadow-${id}`} cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor="#536DFE" stopOpacity="0.55" />
            <stop offset="1" stopColor="#536DFE" stopOpacity="0" />
          </radialGradient>
        </defs>

        <ellipse cx="200" cy="452" rx="130" ry="16" fill={`url(#rb-shadow-${id})`} className="ai-robot-shadow" />

        <line x1="200" y1="52" x2="200" y2="30" stroke={`url(#rb-metal-${id})`} strokeWidth="5" strokeLinecap="round" />
        <circle cx="200" cy="24" r="10" fill="#65DDF4" className="ai-antenna" />
        <circle cx="197" cy="21" r="3" fill="#FFFFFF" opacity="0.9" />

        <rect x="150" y="214" width="100" height="30" rx="12" fill="#AFC0DA" />

        <rect x="104" y="236" width="192" height="180" rx="58" fill={`url(#rb-body-${id})`} stroke="#A9BBD8" strokeWidth="2" />
        <path d="M130 262 Q150 250 170 258" fill="none" stroke="#FFFFFF" strokeWidth="6" strokeLinecap="round" opacity="0.8" />
        <rect x="160" y="300" width="80" height="62" rx="20" fill="#0B1E3B" opacity="0.92" />
        <circle cx="200" cy="331" r="18" fill="none" stroke="#65DDF4" strokeWidth="3" className="ai-core" />
        <circle cx="200" cy="331" r="7" fill={`url(#rb-chest-${id})`} />

        <rect x="66" y="262" width="34" height="112" rx="17" fill={`url(#rb-metal-${id})`} stroke="#A9BBD8" strokeWidth="1.5" className="ai-arm-left" />
        <rect x="300" y="262" width="34" height="112" rx="17" fill={`url(#rb-metal-${id})`} stroke="#A9BBD8" strokeWidth="1.5" className="ai-arm-right" />
        <circle cx="83" cy="382" r="13" fill="#E6EDF8" stroke="#A9BBD8" strokeWidth="1.5" />
        <circle cx="317" cy="382" r="13" fill="#E6EDF8" stroke="#A9BBD8" strokeWidth="1.5" />

        <rect x="88" y="96" width="224" height="160" rx="64" fill={`url(#rb-head-${id})`} stroke="#A9BBD8" strokeWidth="2" />
        <path d="M112 118 Q140 100 176 104" fill="none" stroke="#FFFFFF" strokeWidth="7" strokeLinecap="round" opacity="0.9" />

        <rect x="114" y="132" width="172" height="92" rx="36" fill={`url(#rb-visor-${id})`} />
        <path d="M130 150 Q200 136 270 150" fill="none" stroke="#65DDF4" strokeOpacity="0.25" strokeWidth="2" />

        {closed ? (
          <g stroke="#65DDF4" strokeWidth="5" strokeLinecap="round" fill="none">
            <path d="M152 176 Q163 184 174 176" />
            <path d="M226 176 Q237 184 248 176" />
          </g>
        ) : (
          <g className={`ai-eyes ${alert ? 'ai-eyes-alert' : ''}`}>
            <ellipse cx="162" cy="172" rx="22" ry="26" fill={`url(#rb-eye-${id})`} className="ai-glow" />
            <ellipse cx="162" cy="172" rx="11" ry="15" fill="#65DDF4" className="ai-eye" />
            <ellipse cx="238" cy="172" rx="22" ry="26" fill={`url(#rb-eye-${id})`} className="ai-glow" />
            <ellipse cx="238" cy="172" rx="11" ry="15" fill="#65DDF4" className="ai-eye" />
            <ellipse cx="158" cy="165" rx="3.5" ry="4" fill="#FFFFFF" />
            <ellipse cx="234" cy="165" rx="3.5" ry="4" fill="#FFFFFF" />
          </g>
        )}

        <path d="M186 206 Q200 212 214 206" fill="none" stroke="#65DDF4" strokeWidth="3" strokeLinecap="round" opacity="0.8" />
        <circle cx="104" cy="160" r="5" fill="#65DDF4" opacity="0.8" />
        <circle cx="296" cy="160" r="5" fill="#65DDF4" opacity="0.8" />
      </svg>
    </div>
  )
}

export function Rocket({ className = '' }) {
  const id = useId().replace(/:/g, '')
  return (
    <div className={`ai-rocket ${className}`}>
      <svg viewBox="0 0 120 230" className="ai-rocket-svg" role="img" aria-label="Rocket">
        <defs>
          <linearGradient id={`rk-body-${id}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#9FB3D4" />
            <stop offset="0.45" stopColor="#FFFFFF" />
            <stop offset="1" stopColor="#B9C9E2" />
          </linearGradient>
          <linearGradient id={`rk-fin-${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#536DFE" />
            <stop offset="1" stopColor="#3155D9" />
          </linearGradient>
          <linearGradient id={`rk-flame-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#FFFFFF" />
            <stop offset="0.4" stopColor="#65DDF4" />
            <stop offset="1" stopColor="#536DFE" stopOpacity="0" />
          </linearGradient>
          <radialGradient id={`rk-glass-${id}`} cx="0.35" cy="0.3" r="0.8">
            <stop offset="0" stopColor="#DFF9FF" />
            <stop offset="0.5" stopColor="#65DDF4" />
            <stop offset="1" stopColor="#102A4C" />
          </radialGradient>
        </defs>
        <path className="ai-flame" d="M48 170 Q60 232 72 170 Z" fill={`url(#rk-flame-${id})`} />
        <path d="M30 150 L14 186 L36 176 Z" fill={`url(#rk-fin-${id})`} />
        <path d="M90 150 L106 186 L84 176 Z" fill={`url(#rk-fin-${id})`} />
        <path d="M60 14 C84 40 90 90 88 150 L32 150 C30 90 36 40 60 14 Z" fill={`url(#rk-body-${id})`} stroke="#A9BBD8" strokeWidth="1.5" />
        <path d="M60 14 C74 26 82 42 85 60 L40 60 C43 42 48 26 60 14 Z" fill="#536DFE" opacity="0.9" />
        <circle cx="60" cy="96" r="15" fill={`url(#rk-glass-${id})`} stroke="#FFFFFF" strokeWidth="3" />
        <path d="M52 90 Q56 84 62 84" fill="none" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" opacity="0.8" />
        <rect x="40" y="130" width="40" height="8" rx="3" fill="#65DDF4" opacity="0.7" />
        <path d="M44 150 L40 160 L80 160 L76 150 Z" fill="#3155D9" />
      </svg>
    </div>
  )
}

export function OrbitScene({ className = '', mode = 'idle' }) {
  return (
    <div className={`ai-scene ${className}`} aria-hidden="true">
      <span className="ai-orbit ai-orbit-1" />
      <span className="ai-orbit ai-orbit-2" />
      <span className="ai-particle p1" />
      <span className="ai-particle p2" />
      <span className="ai-particle p3" />
      <span className="ai-particle p4" />
      <span className="ai-particle p5" />
      <AIRobot mode={mode} className="ai-scene-robot" />
      <Rocket className="ai-scene-rocket" />
    </div>
  )
}

export default AIRobot
