import { Pencil } from 'lucide-react'
import { salesApi } from '../../../api/salesApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useAuth } from '../../../hooks/useAuth'
import { formatDate, formatINR, formatNumber } from '../../../utils/formatters'

const show = (v, fmt) => (v === null || v === undefined || v === '' ? '—' : fmt ? fmt(v) : v)

/** A customer's record plus their latest orders (GET /sales/orders/?customer=). */
export default function CustomerDetailsModal({ customer, onClose, onEdit }) {
  if (!customer) return null
  return <Details customer={customer} onClose={onClose} onEdit={onEdit} />
}

function Details({ customer: c, onClose, onEdit }) {
  const { can } = useAuth()
  const canSeeOrders = can('sales')
  const orders = useApi(
    () => (canSeeOrders ? salesApi.listOrders({ customer: c.id, page_size: 5 }) : Promise.resolve(null)),
    [c.id, canSeeOrders],
  )
  const rows = Array.isArray(orders.data?.results) ? orders.data.results : []

  return (
    <Modal
      open
      onClose={onClose}
      title={c.name}
      subtitle={c.type_label || c.type}
      size="lg"
      footer={
        onEdit && (
          <Button variant="outline" icon={Pencil} onClick={() => onEdit(c)}>
            Edit Customer
          </Button>
        )
      }
    >
      <dl className="detail-list">
        <dt>Contact person</dt>
        <dd>{show(c.contact_person)}</dd>
        <dt>Mobile</dt>
        <dd>{c.phone ? <a href={`tel:${c.phone}`}>{c.phone}</a> : '—'}</dd>
        <dt>Email</dt>
        <dd>{c.email ? <a href={`mailto:${c.email}`}>{c.email}</a> : '—'}</dd>
        <dt>City</dt>
        <dd>{show(c.city)}</dd>
        <dt>Address</dt>
        <dd>{show(c.address)}</dd>
        <dt>Total orders</dt>
        <dd>{show(c.total_orders, formatNumber)}</dd>
        <dt>Total purchase</dt>
        <dd>{show(c.total_purchase, formatINR)}</dd>
        <dt>Last order</dt>
        <dd>{show(c.last_order_date, formatDate)}</dd>
        <dt>Status</dt>
        <dd>{c.status ? <Badge>{c.status}</Badge> : '—'}</dd>
      </dl>

      {canSeeOrders && (
        <>
          <h3 className="modal__section-title">Recent orders</h3>
          {orders.error && !orders.loading ? (
            <ErrorMessage message={orders.error.message} onRetry={orders.reload} />
          ) : (
            <Table
              compact
              loading={orders.loading}
              caption={`Recent orders for ${c.name}`}
              data={rows}
              emptyTitle="No orders yet"
              emptyMessage="This customer's orders will appear here."
              columns={[
                { key: 'order_number', header: 'Order ID', render: (r) => r.order_number ?? r.id },
                { key: 'date', header: 'Date', render: (r) => show(r.date, formatDate) },
                { key: 'product', header: 'Product' },
                { key: 'amount', header: 'Amount', align: 'right', render: (r) => show(r.amount, formatINR) },
                { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
              ]}
            />
          )}
        </>
      )}
    </Modal>
  )
}
