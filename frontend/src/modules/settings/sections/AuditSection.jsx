import { History, Search } from 'lucide-react'
import { useState } from 'react'
import { settingsApi } from '../../../api/settingsApi'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { formatDate, formatTime } from '../../../utils/formatters'

const PAGE_SIZE = 15

/** Who changed what, and when (GET /settings/audit-logs/). */
export default function AuditSection() {
  const [search, setSearch] = useState('')
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(query)
  const logs = useApi(() => settingsApi.listAuditLogs({ page, page_size: PAGE_SIZE, search: query }), [page, query])
  const rows = Array.isArray(logs.data?.results) ? logs.data.results : []

  return (
    <Card title="Audit Logs" subtitle="Who changed what, and when" bodyClassName="card__body--flush">
      <div className="toolbar">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search user or action" aria-label="Search audit logs" />
        </label>
      </div>
      {logs.error && !logs.loading ? (
        <div className="card__pad">
          <ErrorMessage message={logs.error.message} onRetry={logs.reload} />
        </div>
      ) : (
        <Table
          compact
          loading={logs.loading}
          caption="Audit logs"
          data={rows}
          emptyIcon={History}
          emptyTitle={query ? 'No entries match your search' : 'No audit entries yet'}
          emptyMessage={query ? 'Try a different search.' : 'Changes made in the portal will be recorded here.'}
          pagination={{ page, pageSize: PAGE_SIZE, total: Number(logs.data?.count) || 0, onPageChange: setPage }}
          columns={[
            { key: 'time', header: 'Time', render: (r) => <span className="nowrap">{r.time ? `${formatDate(r.time)}, ${formatTime(r.time)}` : '—'}</span> },
            { key: 'user', header: 'User', render: (r) => r.user || '—' },
            { key: 'action', header: 'Action', render: (r) => r.action || '—' },
            { key: 'target', header: 'Record', render: (r) => r.target || '—' },
          ]}
        />
      )}
    </Card>
  )
}
