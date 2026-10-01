import { Download, Search, Users } from 'lucide-react'
import { useState } from 'react'
import { customersApi } from '../../../api/customersApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select } from '../../../components/common/Input'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatINR, formatNumber } from '../../../utils/formatters'

const PAGE_SIZE = 10
const has = (v) => v !== null && v !== undefined && v !== ''

/** Customer list: server-side search, status filter, pagination and CSV export. */
export default function CustomersTable({ type, refreshKey, statuses, onView }) {
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [exporting, setExporting] = useState(false)
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(JSON.stringify([type, query, status]))

  const customers = useApi(
    () => customersApi.list({ page, page_size: PAGE_SIZE, search: query, type, status }),
    [page, query, type, status, refreshKey],
  )
  const rows = Array.isArray(customers.data?.results) ? customers.data.results : []
  const total = Number(customers.data?.count) || 0
  const filtered = Boolean(query || status || type)

  const exportList = async () => {
    setExporting(true)
    try {
      await customersApi.exportList({ search: query, type, status })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <Card
      title="Customer Details"
      subtitle={customers.loading ? undefined : `${formatNumber(total)} customer${total === 1 ? '' : 's'}`}
      bodyClassName="card__body--flush"
      action={
        <Button variant="outline" size="sm" icon={Download} onClick={exportList} loading={exporting} disabled={total === 0}>
          Export
        </Button>
      }
    >
      <div className="toolbar">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, city, contact or phone"
            aria-label="Search customers"
          />
        </label>
        <Select
          className="field--inline"
          aria-label="Filter by status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[{ value: '', label: 'All statuses' }, ...(Array.isArray(statuses) ? statuses : [])]}
        />
      </div>

      {customers.error && !customers.loading ? (
        <div className="card__pad">
          <ErrorMessage message={customers.error.message} onRetry={customers.reload} />
        </div>
      ) : (
        <Table
          loading={customers.loading}
          caption="Customers"
          data={rows}
          emptyIcon={Users}
          emptyTitle={filtered ? 'No customers match your filters' : 'No customers yet'}
          emptyMessage={filtered ? 'Try a different search, type or status.' : 'Customers appear here once they are added or imported.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
          columns={[
            {
              key: 'name',
              header: 'Customer',
              // The name opens the details view (keeps the table narrow enough for laptops)
              render: (r) => (
                <button type="button" className="link link--strong table-link" onClick={() => onView(r)}>
                  {r.name}
                </button>
              ),
            },
            { key: 'type', header: 'Type', render: (r) => (r.type_label || r.type ? <Badge tone="blue">{r.type_label || r.type}</Badge> : '—') },
            { key: 'city', header: 'City', render: (r) => r.city || '—' },
            { key: 'phone', header: 'Phone', render: (r) => r.phone || '—' },
            { key: 'total_orders', header: 'Orders', align: 'right', render: (r) => (has(r.total_orders) ? formatNumber(r.total_orders) : '—') },
            { key: 'total_purchase', header: 'Purchases', align: 'right', render: (r) => (has(r.total_purchase) ? formatINR(r.total_purchase) : '—') },
            { key: 'last_order_date', header: 'Last Order', render: (r) => <span className="nowrap">{r.last_order_date ? formatDate(r.last_order_date) : '—'}</span> },
            { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
          ]}
        />
      )}
    </Card>
  )
}
