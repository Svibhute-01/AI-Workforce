import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Maximize, Maximize2, Minimize2, RotateCcw, ZoomIn, ZoomOut } from 'lucide-react'

// Pan / zoom / fit surface shared by every architecture diagram. The content is SVG drawn in its
// own coordinate space; this component only moves and scales it. No external library is used.

const CanvasContext = createContext({ wasDragged: () => false })
export const useCanvas = () => useContext(CanvasContext)

const MIN = 0.1
const MAX = 3
const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))

function DiagramCanvas({ width, height, children, label, resetKey, heightClass = 'h-[480px] sm:h-[640px]', footer }) {
  const [view, setView] = useState({ k: 1, x: 0, y: 0 })
  const [expanded, setExpanded] = useState(false)
  const box = useRef(null)
  const touched = useRef(false)
  const drag = useRef(null)
  const moved = useRef(false)

  const fit = useCallback(() => {
    const el = box.current
    if (!el || !width || !height) return
    const rect = el.getBoundingClientRect()
    if (!rect.width || !rect.height) return
    const k = clamp(Math.min((rect.width - 40) / width, (rect.height - 40) / height), MIN, 1.25)
    setView({ k, x: (rect.width - width * k) / 2, y: (rect.height - height * k) / 2 })
  }, [width, height])

  // Fit whenever the content changes (another diagram, another focus) or the surface is resized,
  // until the person moves the view themselves.
  useLayoutEffect(() => { touched.current = false; fit() }, [fit, resetKey, expanded])
  useEffect(() => {
    const el = box.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver(() => { if (!touched.current) fit() })
    observer.observe(el)
    return () => observer.disconnect()
  }, [fit])

  useEffect(() => {
    const el = box.current
    if (!el) return undefined
    const onWheel = (event) => {
      event.preventDefault()
      touched.current = true
      const rect = el.getBoundingClientRect()
      const px = event.clientX - rect.left
      const py = event.clientY - rect.top
      setView((v) => {
        const k = clamp(v.k * Math.exp(-event.deltaY * 0.0015), MIN, MAX)
        const ratio = k / v.k
        return { k, x: px - (px - v.x) * ratio, y: py - (py - v.y) * ratio }
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  useEffect(() => {
    if (!expanded) return undefined
    const onKey = (event) => { if (event.key === 'Escape') setExpanded(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded])

  const zoomBy = (factor) => {
    const el = box.current
    if (!el) return
    touched.current = true
    const rect = el.getBoundingClientRect()
    const px = rect.width / 2
    const py = rect.height / 2
    setView((v) => {
      const k = clamp(v.k * factor, MIN, MAX)
      const ratio = k / v.k
      return { k, x: px - (px - v.x) * ratio, y: py - (py - v.y) * ratio }
    })
  }
  const actualSize = () => {
    const el = box.current
    if (!el) return
    touched.current = true
    const rect = el.getBoundingClientRect()
    setView({ k: 1, x: Math.max(16, (rect.width - width) / 2), y: Math.max(16, (rect.height - height) / 2) })
  }

  const onPointerDown = (event) => {
    if (event.button !== 0) return
    drag.current = { x: event.clientX, y: event.clientY, vx: view.x, vy: view.y, captured: false, id: event.pointerId }
    moved.current = false
  }
  const onPointerMove = (event) => {
    const d = drag.current
    if (!d) return
    const dx = event.clientX - d.x
    const dy = event.clientY - d.y
    if (!d.captured && Math.hypot(dx, dy) < 5) return
    if (!d.captured) {
      // Only start capturing once it is a real drag, so a plain click still reaches the node.
      d.captured = true
      moved.current = true
      touched.current = true
      event.currentTarget.setPointerCapture?.(d.id)
    }
    setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }))
  }
  const onPointerUp = () => {
    drag.current = null
    setTimeout(() => { moved.current = false }, 0)
  }

  const context = useRef({ wasDragged: () => moved.current })
  const percent = Math.round(view.k * 100)
  const button = 'p-1.5 rounded-md text-text-secondary hover:bg-bg-light hover:text-text-primary transition-colors'

  return (
    <CanvasContext.Provider value={context.current}>
      <div className={expanded ? 'fixed inset-0 z-50 bg-black/40 p-3 sm:p-6 flex' : 'relative'}>
        <div className={`relative bg-white border border-border-light rounded-xl overflow-hidden ${expanded ? 'flex-1' : heightClass}`}>
          <div className="absolute top-2 right-2 z-10 flex items-center gap-0.5 bg-white/95 border border-border-light rounded-lg p-0.5 shadow-sm" role="toolbar" aria-label="Diagram controls">
            <button className={button} onClick={() => zoomBy(1.25)} title="Zoom in" aria-label="Zoom in"><ZoomIn className="w-4 h-4" /></button>
            <button className={button} onClick={() => zoomBy(0.8)} title="Zoom out" aria-label="Zoom out"><ZoomOut className="w-4 h-4" /></button>
            <button className={button} onClick={() => { touched.current = false; fit() }} title="Fit to screen" aria-label="Fit to screen"><Maximize className="w-4 h-4" /></button>
            <button className={button} onClick={actualSize} title="Actual size (100%)" aria-label="Actual size"><RotateCcw className="w-4 h-4" /></button>
            <button className={button} onClick={() => setExpanded((value) => !value)} title={expanded ? 'Close full screen (Esc)' : 'Full screen'} aria-label={expanded ? 'Close full screen' : 'Full screen'}>
              {expanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>
          </div>
          <div
            ref={box}
            data-testid="diagram-canvas"
            data-zoom={view.k.toFixed(3)}
            data-pan={`${Math.round(view.x)},${Math.round(view.y)}`}
            className="absolute inset-0 touch-none cursor-grab active:cursor-grabbing select-none"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            <svg width="100%" height="100%" role="img" aria-label={label}>
              <defs>
                <pattern id="canvas-dots" width="22" height="22" patternUnits="userSpaceOnUse">
                  <circle cx="1.5" cy="1.5" r="1" fill="#e5e0ff" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#canvas-dots)" />
              <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>{children}</g>
            </svg>
          </div>
          <div className="absolute bottom-2 left-3 z-10 text-[11px] text-text-secondary bg-white/90 rounded px-1.5 py-0.5 pointer-events-none">
            {percent}% · scroll to zoom · drag to pan
          </div>
          {footer}
        </div>
      </div>
    </CanvasContext.Provider>
  )
}

export default DiagramCanvas
