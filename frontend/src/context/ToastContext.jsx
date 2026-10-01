import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { ToastContext } from './contexts'

let nextId = 1

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])

  const show = useCallback(
    (message, type = 'success') => {
      const id = nextId++
      setToasts((t) => [...t, { id, message, type }])
      setTimeout(() => dismiss(id), 3500)
    },
    [dismiss],
  )

  const value = useMemo(
    () => ({ success: (m) => show(m, 'success'), error: (m) => show(m, 'error'), info: (m) => show(m, 'info') }),
    [show],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast--${t.type}`}>
            {t.type === 'error' ? <CircleAlert size={18} /> : t.type === 'info' ? <Info size={18} /> : <CircleCheck size={18} />}
            <span>{t.message}</span>
            <button className="icon-btn icon-btn--sm" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
