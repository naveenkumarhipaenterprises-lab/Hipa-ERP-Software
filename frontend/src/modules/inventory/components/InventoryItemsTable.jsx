import { Eye, Package, Search } from 'lucide-react'
import { useState } from 'react'
import { inventoryApi } from '../../../api/inventoryApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select } from '../../../components/common/Input'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { formatDate, formatINR, formatNumber } from '../../../utils/formatters'
import ItemDetailsModal from './ItemDetailsModal'

const PAGE_SIZE = 10
const has = (v) => v !== null && v !== undefined && v !== ''
const kg = (v) => (has(v) ? formatNumber(v) : '—')

/** Product inventory list: server-side search, status filter and pagination, with a details view. */
export default function InventoryItemsTable({ refreshKey, statuses }) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [viewing, setViewing] = useState(null)
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(JSON.stringify([query, status]))

  const items = useApi(() => inventoryApi.listItems({ page, page_size: PAGE_SIZE, search: query, status }), [page, query, status, refreshKey])
  const rows = Array.isArray(items.data?.results) ? items.data.results : []
  const total = Number(items.data?.count) || 0
  const filtered = Boolean(query || status)

  return (
    <Card
      title="Product Inventory Details"
      subtitle={items.loading ? undefined : `${formatNumber(total)} product${total === 1 ? '' : 's'}`}
      bodyClassName="card__body--flush"
    >
      <div className="toolbar">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search products" aria-label="Search products" />
        </label>
        <Select
          className="field--inline"
          aria-label="Filter by stock status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[{ value: '', label: 'All statuses' }, ...(Array.isArray(statuses) ? statuses : [])]}
        />
      </div>

      {items.error && !items.loading ? (
        <div className="card__pad">
          <ErrorMessage message={items.error.message} onRetry={items.reload} />
        </div>
      ) : (
        <Table
          loading={items.loading}
          caption="Product inventory"
          data={rows}
          emptyIcon={Package}
          emptyTitle={filtered ? 'No products match your filters' : 'No products in inventory'}
          emptyMessage={filtered ? 'Try a different search or status.' : 'Products appear here once they are added.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
          columns={[
            { key: 'product', header: 'Product', render: (r) => <strong>{r.product}</strong> },
            { key: 'stock_kg', header: 'Stock (kg)', align: 'right', render: (r) => kg(r.stock_kg) },
            { key: 'min_stock_kg', header: 'Min (kg)', align: 'right', render: (r) => kg(r.min_stock_kg) },
            { key: 'reorder_level_kg', header: 'Reorder (kg)', align: 'right', render: (r) => kg(r.reorder_level_kg) },
            { key: 'stock_value', header: 'Stock Value', align: 'right', render: (r) => (has(r.stock_value) ? formatINR(r.stock_value) : '—') },
            { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
            { key: 'updated_at', header: 'Last Updated', render: (r) => (r.updated_at ? formatDate(r.updated_at) : '—') },
            {
              key: 'view',
              sticky: true,
              header: <span className="sr-only">Details</span>,
              align: 'right',
              render: (r) => (
                <Button size="sm" variant="soft" icon={Eye} onClick={() => setViewing(r)} aria-label={`View ${r.product}`}>
                  View
                </Button>
              ),
            },
          ]}
        />
      )}

      <ItemDetailsModal item={viewing} onClose={() => setViewing(null)} />
    </Card>
  )
}
