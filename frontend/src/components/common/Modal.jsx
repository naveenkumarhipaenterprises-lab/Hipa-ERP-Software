import { X } from 'lucide-react'
import { useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useFocusTrap } from '../../hooks/useFocusTrap'

// Focus the first form control, or the first action button other than close
const firstControl = (panel) =>
  panel?.querySelector('input, select, textarea') ?? panel?.querySelector('.modal__footer button, .modal__body button')

/**
 * Accessible dialog: Escape and backdrop click close it, Tab stays inside it,
 * and focus returns to the element that opened it.
 */
export default function Modal({ open, onClose, title, subtitle, children, footer, size = 'md', closeOnBackdrop = true }) {
  const titleId = useId()
  const panelRef = useRef(null)
  useFocusTrap(panelRef, open, { onEscape: onClose, initialFocus: firstControl })

  if (!open) return null

  return createPortal(
    <div className="modal-backdrop" onMouseDown={(e) => closeOnBackdrop && e.target === e.currentTarget && onClose()}>
      <div ref={panelRef} className={`modal modal--${size}`} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        <header className="modal__header">
          <div>
            <h2 id={titleId} className="modal__title">
              {title}
            </h2>
            {subtitle && <p className="modal__subtitle">{subtitle}</p>}
          </div>
          <button type="button" className="icon-btn modal__close" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </header>
        <div className="modal__body">{children}</div>
        {footer && <footer className="modal__footer">{footer}</footer>}
      </div>
    </div>,
    document.body,
  )
}
