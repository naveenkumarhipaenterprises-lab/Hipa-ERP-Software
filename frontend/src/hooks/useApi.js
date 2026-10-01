import { useCallback, useEffect, useEffectEvent, useState } from 'react'

/**
 * Loads data from an API function and tracks loading / error state.
 *
 *   const { data, loading, error, reload, setData } = useApi(() => salesApi.getOverview({ range }), [range])
 *
 * Previous data stays visible while a reload is in flight.
 */
export function useApi(fetcher, deps = []) {
  const [tick, setTick] = useState(0)
  const [result, setResult] = useState({ key: null, data: null, error: null })
  const key = `${JSON.stringify(deps)}#${tick}`

  const run = useEffectEvent(() => fetcher())

  useEffect(() => {
    let active = true
    run().then(
      (data) => active && setResult({ key, data, error: null }),
      (error) => active && setResult((r) => ({ key, data: r.data, error })),
    )
    return () => {
      active = false
    }
  }, [key])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  const setData = useCallback(
    (updater) => setResult((r) => ({ ...r, data: typeof updater === 'function' ? updater(r.data) : updater })),
    [],
  )

  return { data: result.data, error: result.error, loading: result.key !== key, reload, setData }
}
