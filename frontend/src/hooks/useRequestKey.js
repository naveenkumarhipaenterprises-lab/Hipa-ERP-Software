import { useState } from 'react'

const newKey = () =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`

/**
 * A one-time code for a form that records money (a payment). It is new each time the form opens and stays the same
 * while it is open, so a double click or a retry after a slow connection can't record the payment twice: the server
 * refuses a code it has just seen (services/once.py). Send it as `request_key`.
 */
export function useRequestKey(open) {
  const [state, setState] = useState({ open: false, key: null })
  if (open !== state.open) {
    const next = { open, key: open ? newKey() : null }
    setState(next) // a new code for every opening (React allows this update during render)
    return next.key
  }
  return state.key
}
