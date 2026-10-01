import ProgressList from '../../../components/charts/ProgressList'
import { formatNumber } from '../../../utils/formatters'

// Styling only: colour by status name, grey for anything else
const STATUS_COLORS = {
  delivered: 'var(--green-600)',
  completed: 'var(--green-600)',
  'in transit': 'var(--blue-600)',
  shipped: 'var(--blue-600)',
  processing: 'var(--amber-600)',
  pending: 'var(--amber-600)',
  cancelled: 'var(--red-600)',
  returned: 'var(--red-600)',
}

/** Order counts by status from the API: [{ status, count }] */
export default function OrderStatusList({ items }) {
  const rows = Array.isArray(items) ? items.filter((r) => r && r.status) : []
  const total = rows.reduce((sum, r) => sum + (Number(r.count) || 0), 0)
  return (
    <>
      <ProgressList
        items={rows.map((r) => ({
          name: r.status,
          value: Number(r.count) || 0,
          color: STATUS_COLORS[String(r.status).toLowerCase()] ?? 'var(--muted)',
        }))}
        max={total || 1}
        format={formatNumber}
        emptyTitle="No orders in this period"
        emptyMessage="Order counts by status will appear here."
      />
      {total > 0 && <p className="order-status__total">Total orders: <strong>{formatNumber(total)}</strong></p>}
    </>
  )
}
