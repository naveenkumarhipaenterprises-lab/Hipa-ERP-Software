import { useEffect, useEffectEvent } from 'react'

/**
 * While `open`, closes on a click outside `ref` or on Escape.
 * Escape also returns focus to `triggerRef` so keyboard users don't lose their place.
 */
export function useDismiss(ref, open, onClose, triggerRef) {
  const close = useEffectEvent((restoreFocus) => {
    onClose()
    if (restoreFocus) triggerRef?.current?.focus()
  })

  useEffect(() => {
    if (!open) return undefined
    const onPointer = (e) => ref.current && !ref.current.contains(e.target) && close(false)
    const onKey = (e) => e.key === 'Escape' && close(true)
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [ref, open])
}
