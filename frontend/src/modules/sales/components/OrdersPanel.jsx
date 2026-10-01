import { Search, ShoppingCart, XCircle } from 'lucide-react'
import { useState } from 'react'
import { salesApi } from '../../../api/salesApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
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

/**
 * Orders list: server-side search, status filter and pagination (DRF { count, results }).
 * Cancelling is offered only where the backend marks the order `can_cancel`.
 */
export default function OrdersPanel({ range, product, rangeLabel, refreshKey, statuses, canManage, onChanged }) {
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [cancelling, setCancelling] = useState(null)
  const query = useDebouncedValue(search.trim())

  // Any filter change sends the list back to page 1
  const [page, setPage] = usePageReset(JSON.stringify([range, product, query, status]))

  const orders = useApi(
    () => salesApi.listOrders({ page, page_size: PAGE_SIZE, search: query, status, range, product }),
    [page, query, status, range, product, refreshKey],
  )
  const rows = Array.isArray(orders.data?.results) ? orders.data.results : []
  const total = Number(orders.data?.count) || 0
  const filtered = Boolean(query || status)

  const confirmCancel = async () => {
    await salesApi.cancelOrder(cancelling.id)
    toast.success(`Order ${cancelling.order_number ?? cancelling.id} cancelled`)
    // Refreshes this list and the overview figures
    if (onChanged) onChanged()
    else orders.reload()
  }

  const columns = [
    { key: 'order_number', header: 'Order ID', render: (r) => <strong>{r.order_number ?? r.id}</strong> },
    { key: 'date', header: 'Date', render: (r) => (r.date ? formatDate(r.date) : '—') },
    { key: 'customer', header: 'Customer' },
    { key: 'product', header: 'Product' },
    { key: 'quantity_kg', header: 'Qty (kg)', align: 'right', render: (r) => (has(r.quantity_kg) ? formatNumber(r.quantity_kg) : '—') },
    { key: 'amount', header: 'Amount', align: 'right', render: (r) => (has(r.amount) ? formatINR(r.amount) : '—') },
    { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
  ]
  if (canManage) {
    columns.push({
      key: 'actions',
      sticky: true,
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      render: (r) =>
        r.can_cancel === true && (
          <Button variant="ghost" size="sm" icon={XCircle} className="btn--tone-red" onClick={() => setCancelling(r)}>
            Cancel
          </Button>
        ),
    })
  }

  return (
    <Card
      title="Orders"
      subtitle={orders.loading ? rangeLabel : `${formatNumber(total)} order${total === 1 ? '' : 's'} • ${rangeLabel}`}
      bodyClassName="card__body--flush"
    >
      <div className="toolbar">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by order ID or customer"
            aria-label="Search orders"
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

      {orders.error && !orders.loading ? (
        <div className="card__pad">
          <ErrorMessage message={orders.error.message} onRetry={orders.reload} />
        </div>
      ) : (
        <Table
          loading={orders.loading}
          caption="Orders"
          data={rows}
          columns={columns}
          emptyIcon={ShoppingCart}
          emptyTitle={filtered ? 'No orders match your filters' : 'No orders in this period'}
          emptyMessage={filtered ? 'Try a different search or status.' : 'Orders will be listed here once they are created.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
        />
      )}

      <ConfirmDialog
        open={Boolean(cancelling)}
        onClose={() => setCancelling(null)}
        onConfirm={confirmCancel}
        danger
        title="Cancel this order?"
        message={
          cancelling &&
          `Order ${cancelling.order_number ?? cancelling.id}${cancelling.customer ? ` for ${cancelling.customer}` : ''} will be cancelled. This cannot be undone.`
        }
        confirmLabel="Cancel Order"
        cancelLabel="Keep Order"
      />
    </Card>
  )
}
