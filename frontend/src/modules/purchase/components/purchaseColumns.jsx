import Badge from '../../../components/common/Badge'
import { date, money, qty } from '../shared'

/** Table columns for purchases, shared by the purchase list, supplier details and the overview. */
export const PURCHASE_COLUMNS = [
  { key: 'purchase_number', header: 'Purchase ID', render: (r) => <strong className="nowrap">{r.purchase_number}</strong> },
  { key: 'purchase_date', header: 'Date', render: (r) => <span className="nowrap">{date(r.purchase_date)}</span> },
  { key: 'supplier', header: 'Supplier' },
  { key: 'item', header: 'Material / Product' },
  { key: 'quantity', header: 'Quantity', align: 'right', render: (r) => qty(r.quantity, r.unit) },
  { key: 'total_amount', header: 'Total', align: 'right', render: (r) => money(r.total_amount) },
  { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
  { key: 'payment_status', header: 'Payment', render: (r) => (r.payment_status ? <Badge>{r.payment_status}</Badge> : '—') },
]
