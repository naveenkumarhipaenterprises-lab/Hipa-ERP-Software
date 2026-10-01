import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import EmptyState from './EmptyState'

/**
 * Data table with loading, empty and paginated states.
 *
 * columns: [{ key, header, render?(row, index), align?: 'left'|'right'|'center', width?, sticky? }]
 * sticky: pins the column to the right edge, so row actions stay visible when the table scrolls sideways
 * rowKey: a field that is unique per row (default 'id'; the row's position is used when it is missing),
 *         or (row, index) => key. Never a display name: two customers or products can share one.
 *
 * Pagination (optional), either:
 *  - client side: pageSize={10} pages through `data` locally
 *  - server side: pagination={{ page, pageSize, total, onPageChange }} where
 *    `data` is the current page from the API and `page` starts at 1
 */
export default function Table({
  columns,
  data = [],
  rowKey = 'id',
  loading = false,
  emptyTitle = 'No records available',
  emptyMessage = 'Records will appear here once data is available.',
  emptyIcon,
  pageSize,
  pagination,
  numbered = false,
  rowClassName,
  compact = false,
  caption,
}) {
  const [localPage, setLocalPage] = useState(0)

  let rows = data
  let offset = 0
  let pager = null

  if (pagination) {
    const pages = Math.max(1, Math.ceil(pagination.total / pagination.pageSize))
    const page = Math.min(Math.max(1, pagination.page), pages)
    offset = (page - 1) * pagination.pageSize
    pager = { page, pages, total: pagination.total, go: pagination.onPageChange }
  } else if (pageSize) {
    const pages = Math.max(1, Math.ceil(data.length / pageSize))
    const page = Math.min(localPage, pages - 1) + 1
    offset = (page - 1) * pageSize
    rows = data.slice(offset, offset + pageSize)
    pager = { page, pages, total: data.length, go: (p) => setLocalPage(p - 1) }
  }

  const colCount = columns.length + (numbered ? 1 : 0)
  const showEmpty = !loading && data.length === 0

  return (
    <div className="table-wrap">
      <div className="table-scroll">
        <table className={`table ${compact ? 'table--compact' : ''}`} aria-busy={loading || undefined}>
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr>
              {numbered && <th className="table__num" scope="col">#</th>}
              {columns.map((c) => (
                <th key={c.key} scope="col" className={c.sticky ? 'table__sticky' : undefined} style={{ width: c.width, textAlign: c.align }}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading &&
              Array.from({ length: 5 }, (_, i) => (
                <tr key={`sk-${i}`} className="table__skeleton-row" aria-hidden>
                  {Array.from({ length: colCount }, (__, j) => (
                    <td key={j}>
                      <span className="table__skeleton" />
                    </td>
                  ))}
                </tr>
              ))}
            {!loading &&
              rows.map((row, i) => (
                <tr key={typeof rowKey === 'function' ? rowKey(row, offset + i) : row[rowKey] ?? offset + i} className={rowClassName?.(row)}>
                  {numbered && <td className="table__num">{offset + i + 1}</td>}
                  {columns.map((c) => (
                    <td key={c.key} className={c.sticky ? 'table__sticky' : undefined} style={{ textAlign: c.align }}>
                      {c.render ? c.render(row, offset + i) : row[c.key]}
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
        {showEmpty && <EmptyState compact icon={emptyIcon} title={emptyTitle} message={emptyMessage} />}
      </div>

      {pager && !loading && pager.total > 0 && pager.pages > 1 && (
        <nav className="table-pager" aria-label="Table pagination">
          <span>
            Showing {offset + 1}–{offset + (pagination ? data.length : rows.length)} of {pager.total}
          </span>
          <div className="table-pager__btns">
            <button type="button" className="icon-btn" disabled={pager.page <= 1} onClick={() => pager.go(pager.page - 1)} aria-label="Previous page">
              <ChevronLeft size={16} />
            </button>
            <span aria-current="page">
              Page {pager.page} of {pager.pages}
            </span>
            <button type="button" className="icon-btn" disabled={pager.page >= pager.pages} onClick={() => pager.go(pager.page + 1)} aria-label="Next page">
              <ChevronRight size={16} />
            </button>
          </div>
        </nav>
      )}
    </div>
  )
}
