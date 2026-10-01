import { useCallback, useSyncExternalStore } from 'react'

/** True while the CSS media query matches, e.g. useMediaQuery('(max-width: 1024px)'). */
export function useMediaQuery(query) {
  const subscribe = useCallback(
    (notify) => {
      const mql = window.matchMedia(query)
      mql.addEventListener('change', notify)
      return () => mql.removeEventListener('change', notify)
    },
    [query],
  )
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches)
}
