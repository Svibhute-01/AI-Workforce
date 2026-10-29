import { useEffect } from 'react'
import { X } from 'lucide-react'

function Modal({ isOpen, title, children, onClose, onSubmit, submitText = 'Create', submitting = false }) {
  useEffect(() => {
    if (!isOpen) return undefined
    const onKey = (event) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="bt-modal-backdrop fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="card bt-page flex max-h-full w-full max-w-md flex-col">
        <div className="flex shrink-0 items-center justify-between border-b border-border-light px-6 py-4">
          <h2 className="text-lg font-extrabold text-text-primary">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1 text-text-secondary transition-colors hover:bg-brand-soft hover:text-text-primary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="overflow-y-auto p-6">
          {children}
        </div>

        <div className="flex shrink-0 gap-3 border-t border-border-light px-6 py-4">
          <button onClick={onClose} className="btn-secondary flex-1">
            Cancel
          </button>
          <button onClick={onSubmit} disabled={submitting} className="btn-primary flex-1">
            {submitting ? 'Saving...' : submitText}
          </button>
        </div>
      </div>
    </div>
  )
}

export default Modal
