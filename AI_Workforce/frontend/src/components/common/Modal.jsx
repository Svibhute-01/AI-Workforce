import { X } from 'lucide-react'

function Modal({ isOpen, title, children, onClose, onSubmit, submitText = 'Create' }) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg max-w-md w-full mx-4">
        <div className="flex items-center justify-between p-6 border-b border-border-light">
          <h2 className="text-lg font-bold text-text-primary">{title}</h2>
          <button
            onClick={onClose}
            className="text-text-secondary hover:text-text-primary transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          {children}
        </div>

        <div className="flex gap-3 p-6 border-t border-border-light">
          <button
            onClick={onClose}
            className="btn-secondary flex-1"
          >
            Cancel
          </button>
          <button
            onClick={onSubmit}
            className="btn-primary flex-1"
          >
            {submitText}
          </button>
        </div>
      </div>
    </div>
  )
}

export default Modal
