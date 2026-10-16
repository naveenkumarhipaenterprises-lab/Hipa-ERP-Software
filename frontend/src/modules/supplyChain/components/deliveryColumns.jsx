import { Eye } from 'lucide-react'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import { formatDate } from '../../../utils/formatters'

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
