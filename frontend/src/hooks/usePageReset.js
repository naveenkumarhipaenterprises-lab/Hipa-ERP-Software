import { useState } from 'react'

/**
 * Page number for a server-paginated list that returns to page 1 whenever
 * `filterKey` (e.g. JSON of the search and filters) changes.
 */
export function usePageReset(filterKey) {
  const [page, setPage] = useState(1)
  const [key, setKey] = useState(filterKey)
  if (key !== filterKey) {
    setKey(filterKey)
    setPage(1)
  }
  return [page, setPage]
}
