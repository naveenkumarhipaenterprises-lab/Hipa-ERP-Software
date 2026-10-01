import Badge from '../../../components/common/Badge'
import { formatDate } from '../../../utils/formatters'

/** Table columns for shipments, shared by the Recent Shipments card and the tracking dialog. */
export const SHIPMENT_COLUMNS = [
  { key: 'shipment_number', header: 'Shipment ID', render: (r) => <strong>{r.shipment_number ?? r.id}</strong> },
  { key: 'supplier', header: 'Supplier', render: (r) => r.supplier || '—' },
  { key: 'item', header: 'Item', render: (r) => (r.item ? `${r.item}${r.quantity != null ? ` · ${r.quantity} ${r.unit ?? ''}` : ''}` : '—') },
  { key: 'purchase_number', header: 'Purchase', render: (r) => r.purchase_number || '—' },
  { key: 'destination', header: 'Destination', render: (r) => r.destination || '—' },
  { key: 'eta', header: 'ETA', render: (r) => <span className="nowrap">{r.eta ? formatDate(r.eta) : '—'}</span> },
  { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
]
