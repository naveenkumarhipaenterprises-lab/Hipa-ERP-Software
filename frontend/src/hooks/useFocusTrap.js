import { useEffect, useEffectEvent } from 'react'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * While `active`: Tab cycles inside `ref`, Escape calls `onEscape`, the page behind
 * stops scrolling, and focus moves in (to `initialFocus(panel)` or the panel itself).
 * When it ends, focus returns to whatever had it before.
 */
export function useFocusTrap(ref, active, { onEscape, initialFocus } = {}) {
  const escape = useEffectEvent(() => onEscape?.())
  const pickInitial = useEffectEvent((panel) => initialFocus?.(panel))

  useEffect(() => {
    if (!active) return undefined
    const opener = document.activeElement
    const panel = ref.current

    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        escape()
        return
      }
      if (e.key !== 'Tab' || !panel) return
      const items = [...panel.querySelectorAll(FOCUSABLE)]
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    ;(pickInitial(panel) ?? panel)?.focus()

    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      if (opener instanceof HTMLElement && document.contains(opener)) opener.focus()
    }
  }, [ref, active])
}
