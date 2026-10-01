import { PackageCheck, TriangleAlert } from 'lucide-react'
import EmptyState from '../../../components/common/EmptyState'
import { formatKg } from '../../../utils/formatters'

/** Items below their reorder level, as reported by the API: [{ id, product, stock_kg, reorder_level_kg, severity }] */
export default function LowStockAlerts({ items }) {
  const rows = Array.isArray(items) ? items : []
  if (rows.length === 0) {
    return <EmptyState compact icon={PackageCheck} title="No low stock alerts" message="All products are above their reorder level." />
  }
  return (
    <ul className="alert-list">
      {rows.map((i, idx) => {
        const critical = i.severity === 'critical'
        return (
          <li key={i.id ?? idx} className={`alert-row alert-row--${critical ? 'red' : 'amber'}`}>
            <TriangleAlert size={20} aria-hidden />
            <div>
              <strong>{i.product}</strong>
              <span>
                {critical ? 'Critical' : 'Low'}
                {i.reorder_level_kg != null && ` • reorder at ${formatKg(i.reorder_level_kg)}`}
              </span>
            </div>
            <strong className="alert-row__qty">{i.stock_kg != null ? formatKg(i.stock_kg) : '—'}</strong>
          </li>
        )
      })}
    </ul>
  )
}
