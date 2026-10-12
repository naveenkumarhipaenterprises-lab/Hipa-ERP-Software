import { ArrowRightCircle, Eye, ReceiptText, Search, ShoppingCart, Truck, XCircle } from 'lucide-react'
import { useState } from 'react'
import { salesApi } from '../../../api/salesApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select } from '../../../components/common/Input'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import TotalsSummary from '../../../components/common/TotalsSummary'
import { ITEM_COLUMNS } from './documentColumns'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatINR, formatNumber } from '../../../utils/formatters'
import DeleteRecordButton from '../../../components/common/DeleteRecordButton'
import { useAuth } from '../../../hooks/useAuth'
import { DELIVERY_MANAGERS, DELIVERY_VIEWERS, hasAnyRole } from '../../../utils/constants'
import DeliveryDetailsModal from '../../supplyChain/components/DeliveryDetailsModal'

const PAGE_SIZE = 10
const has = (v) => v !== null && v !== undefined && v !== ''

/**
 * Orders list: server-side search, status filter and pagination (DRF { count, results }).
 * Cancelling is offered only where the backend marks the order `can_cancel`; the status moves forward
 * one step at a time to the backend's `next_status`.
 */
export default function OrdersPanel({ range, product, rangeLabel, refreshKey, statuses, canManage, onChanged }) {
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [cancelling, setCancelling] = useState(null)
  const [invoicing, setInvoicing] = useState(null)
  const [viewing, setViewing] = useState(null)
  const [advancing, setAdvancing] = useState(null)
  const [delivery, setDelivery] = useState(null) // order id whose delivery details are open
  const { user } = useAuth()
  // Delivery status uses the same rule as Supply Chain -> Customer Deliveries
  const canSeeDelivery = hasAnyRole(user, DELIVERY_VIEWERS)
  const canManageDelivery = hasAnyRole(user, DELIVERY_MANAGERS)
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

  const advance = async () => {
    const next = advancing.next_status
    await salesApi.setOrderStatus(advancing.id, next.value)
    toast.success(`Order ${advancing.order_number ?? advancing.id} marked ${next.label}`)
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
  columns.splice(6, 0, { key: 'invoice_number', header: 'Invoice', render: (r) => r.invoice_number || '—' })
  columns.push({ key: 'delivery_status', header: 'Delivery', render: (r) => (r.delivery_status ? <Badge>{r.delivery_status}</Badge> : '—') })
  columns.push({
    key: 'actions',
    sticky: true,
    header: <span className="sr-only">Actions</span>,
    align: 'right',
    render: (r) => (
      <span className="row-actions">
        <Button variant="ghost" size="sm" icon={Eye} onClick={() => setViewing(r)} aria-label={`View order ${r.order_number ?? r.id}`} />
        {canSeeDelivery && r.delivery_status && (
          <Button variant="ghost" size="sm" icon={Truck} onClick={() => setDelivery(r.id)} aria-label={`Delivery details of ${r.order_number ?? r.id}`} />
        )}
        {canManage && r.next_status && (
          <Button variant="ghost" size="sm" icon={ArrowRightCircle} onClick={() => setAdvancing(r)} aria-label={`Mark ${r.order_number ?? r.id} ${r.next_status.label}`} />
        )}
        {canManage && r.can_invoice === true && (
          <Button variant="ghost" size="sm" icon={ReceiptText} onClick={() => setInvoicing(r)} aria-label={`Convert ${r.order_number ?? r.id} to a sales invoice`} />
        )}
        {canManage && r.can_cancel === true && (
          <Button variant="ghost" size="sm" icon={XCircle} className="btn--tone-red" onClick={() => setCancelling(r)}>
            Cancel
          </Button>
        )}
        <DeleteRecordButton kind="sales_order" id={r.id} label={r.order_number ?? 'Order'} onDeleted={() => (onChanged ? onChanged() : orders.reload())} />
      </span>
    ),
  })

  const invoice = async () => {
    const inv = await salesApi.orderToInvoice(invoicing.id)
    toast.success(`Sales invoice ${inv.invoice_number} created from ${invoicing.order_number}`)
    if (onChanged) onChanged()
    else orders.reload()
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
      <ConfirmDialog
        open={Boolean(invoicing)}
        onClose={() => setInvoicing(null)}
        onConfirm={invoice}
        title="Convert to sales invoice?"
        message={invoicing && `A new invoice is created for ${invoicing.order_number} with the same products, prices, discounts and GST. Stock already went out with the order, so it does not change.`}
        confirmLabel="Create Invoice"
        cancelLabel="Back"
      />
      <ConfirmDialog
        open={Boolean(advancing)}
        onClose={() => setAdvancing(null)}
        onConfirm={advance}
        title={advancing ? `Mark as ${advancing.next_status?.label}?` : ''}
        message={advancing && `Order ${advancing.order_number ?? advancing.id} moves from ${advancing.status} to ${advancing.next_status?.label}. Orders only move forward${advancing.next_status?.value === 'delivered' ? '; Delivered is final' : ''}.`}
        confirmLabel={advancing ? `Mark ${advancing.next_status?.label}` : 'Confirm'}
        cancelLabel="Back"
      />
      <OrderDetail order={viewing} onClose={() => setViewing(null)} />
      <DeliveryDetailsModal orderId={delivery} canManage={canManageDelivery} onClose={() => setDelivery(null)}
                            onChanged={() => (onChanged ? onChanged() : orders.reload())} />
    </Card>
  )
}

function OrderDetail({ order, onClose }) {
  const detail = useApi(() => (order ? salesApi.getOrder(order.id) : Promise.resolve(null)), [order?.id])
  if (!order) return null
  const o = detail.data
  return (
    <Modal open onClose={onClose} size="lg" title={`Order ${order.order_number ?? order.id}`} subtitle={order.customer}>
      {detail.error && !detail.loading ? (
        <ErrorMessage message={detail.error.message} onRetry={detail.reload} />
      ) : !o ? (
        <Loader label="Loading order…" />
      ) : (
        <div className="stack">
          <dl className="detail-grid">
            {[['Date', o.date ? formatDate(o.date) : '—'], ['Status', <Badge key="s">{o.status}</Badge>], ['Quotation', o.quotation_number || '—'],
              ['Invoice', o.invoice_number || '—'],
              ['Delivery', o.delivery_status ? <Badge key="d">{o.delivery_status}</Badge> : '—'],
              ['Expected Delivery', o.expected_delivery_date ? formatDate(o.expected_delivery_date) : '—'],
              ['Tracking Ref.', o.tracking_reference || '—'],
              ['Delivered On', o.delivered_on ? formatDate(o.delivered_on) : '—'],
              ['Notes', o.notes || '—']].map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
          <Table compact caption="Order products" data={Array.isArray(o.items) ? o.items : []} columns={ITEM_COLUMNS} />
          <TotalsSummary totals={{ subtotal: o.subtotal, discount: o.discount_amount, gst: o.gst_amount, total: o.amount }} totalLabel="Order Total" />
        </div>
      )}
    </Modal>
  )
}
