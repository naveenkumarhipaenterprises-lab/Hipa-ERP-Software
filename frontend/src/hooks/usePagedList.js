import { useState } from 'react'
import { useApi } from './useApi'
import { useDebouncedValue } from './useDebouncedValue'
import { usePageReset } from './usePageReset'

/**
 * State for a server-paginated, searchable, filterable list:
 *   const l = usePagedList((params) => api.listX(params), { status: '' }, refreshKey)
 *   l.search / l.setSearch, l.filters / l.setFilter(name, value), l.rows, l.total, l.page / l.setPage, l.result (useApi)
 * Changing the search or a filter goes back to page 1.
 */
export function usePagedList(fetcher, initialFilters = {}, refreshKey = 0, pageSize = 10) {
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState(initialFilters)
  const query = useDebouncedValue(search)
  const filterKey = JSON.stringify([query, filters])
  const [page, setPage] = usePageReset(filterKey)
  const result = useApi(() => fetcher({ page, page_size: pageSize, search: query, ...filters }), [page, filterKey, refreshKey])
  const rows = Array.isArray(result.data?.results) ? result.data.results : []
  return {
    search,
    setSearch,
    filters,
    setFilter: (name, value) => setFilters((f) => ({ ...f, [name]: value })),
    filtered: Boolean(query) || Object.values(filters).some(Boolean),
    page,
    setPage,
    pageSize,
    rows,
    total: Number(result.data?.count) || 0,
    result,
  }
}
