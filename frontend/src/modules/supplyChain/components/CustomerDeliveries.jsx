import { Eye, Search, Truck } from 'lucide-react'
import { useState } from 'react'
import { supplyChainApi } from '../../../api/supplyChainApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { formatDate } from '../../../utils/formatters'

const PAGE_SIZE = 10

// Same keys and labels as the backend (apps/supply_chain/deliveries.py)
export const DELIVERY_STATUSES = [
  { value: 'pending', label: 'Pending' },
  { value: 'in_transit', label: 'In Transit' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'delayed', label: 'Delayed' },
]

/** Table columns for customer deliveries; `onView(row)` opens the order's delivery details. */
export const deliveryColumns = (onView) => [
  { key: 'order_number', header: 'Sales Order', render: (r) => <strong>{r.order_number}</strong> },
  { key: 'customer', header: 'Customer', render: (r) => r.customer || '—' },
  { key: 'order_date', header: 'Order Date', render: (r) => <span className="nowrap">{r.order_date ? formatDate(r.order_date) : '—'}</span> },
  { key: 'delivery_status', header: 'Delivery Status', render: (r) => (r.delivery_status ? <Badge>{r.delivery_status}</Badge> : '—') },
  { key: 'expected_delivery_date', header: 'Expected Delivery', render: (r) => <span className="nowrap">{r.expected_delivery_date ? formatDate(r.expected_delivery_date) : '—'}</span> },
  { key: 'tracking_reference', header: 'Tracking Ref.', render: (r) => r.tracking_reference || '—' },
  {
    key: 'actions', sticky: true, align: 'right', header: <span className="sr-only">Actions</span>,
    render: (r) => <Button size="sm" variant="ghost" icon={Eye} onClick={() => onView(r)} aria-label={`View delivery of ${r.order_number}`} />,
  },
]

/** Every customer delivery with search, status filter and server pagination. */
export function CustomerDeliveriesModal({ open, refreshKey, onView, onClose }) {
  if (!open) return null
  return <Deliveries refreshKey={refreshKey} onView={onView} onClose={onClose} />
}

function Deliveries({ refreshKey, onView, onClose }) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(JSON.stringify([query, status]))
  const list = useApi(() => supplyChainApi.listCustomerDeliveries({ page, page_size: PAGE_SIZE, search: query, status }), [page, query, status, refreshKey])
  const rows = Array.isArray(list.data?.results) ? list.data.results : []
  const filtered = Boolean(query || status)

  return (
    <Modal open onClose={onClose} title="Customer Deliveries" subtitle="Every sales order that is not cancelled" size="lg">
      <div className="toolbar toolbar--flush">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search order, customer or tracking ref." aria-label="Search customer deliveries" />
        </label>
        <Select className="field--inline" aria-label="Filter by delivery status" value={status} onChange={(e) => setStatus(e.target.value)}
                options={[{ value: '', label: 'All statuses' }, ...DELIVERY_STATUSES]} />
      </div>
      {list.error && !list.loading ? (
        <ErrorMessage message={list.error.message} onRetry={list.reload} />
      ) : (
        <Table
          compact
          loading={list.loading}
          caption="Customer deliveries"
          data={rows}
          columns={deliveryColumns(onView)}
          emptyIcon={Truck}
          emptyTitle={filtered ? 'No deliveries match your filters' : 'No customer orders yet'}
          emptyMessage={filtered ? 'Try a different search or status.' : 'Sales orders appear here for delivery tracking once they are created.'}
          pagination={{ page, pageSize: PAGE_SIZE, total: Number(list.data?.count) || 0, onPageChange: setPage }}
        />
      )}
    </Modal>
  )
}
