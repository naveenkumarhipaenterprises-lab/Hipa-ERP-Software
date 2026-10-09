import { ArrowDown, ArrowLeftRight, ArrowUp, Trash2 } from 'lucide-react'
import Button from '../../../components/common/Button'
import EmptyState from '../../../components/common/EmptyState'
import { formatKg, formatRelativeTime } from '../../../utils/formatters'

/**
 * Stock movements from the API: [{ id, type: 'in' | 'out', product, quantity_kg, created_at, note?, can_delete }]
 * `onDelete` (Super Admins): a delete button on hand-entered movements; the server puts the stock back.
 */
export default function MovementList({ items, showProduct = true, onDelete, emptyMessage = 'Stock in and stock out records will appear here.' }) {
  const rows = Array.isArray(items) ? items : []
  if (rows.length === 0) {
    return <EmptyState compact icon={ArrowLeftRight} title="No stock movements yet" message={emptyMessage} />
  }
  return (
    <ul className="movement-list">
      {rows.map((m, idx) => {
        const isIn = m.type === 'in'
        return (
          <li key={m.id ?? idx}>
            <span className={`movement-list__icon ${isIn ? 'text-up' : 'text-down'}`} aria-hidden>
              {isIn ? <ArrowUp size={18} /> : <ArrowDown size={18} />}
            </span>
            <span className="movement-list__body">
              <strong>
                Stock {isIn ? 'In' : 'Out'}
                {showProduct && m.product ? ` • ${m.product}` : ''}
              </strong>
              <small>{[m.created_at && formatRelativeTime(m.created_at), m.note].filter(Boolean).join(' • ')}</small>
            </span>
            <strong className={isIn ? 'text-up' : 'text-down'}>
              {isIn ? '+' : '−'}
              {formatKg(m.quantity_kg)}
            </strong>
            {onDelete && m.can_delete && (
              <Button size="sm" variant="ghost" icon={Trash2} className="btn--tone-red" onClick={() => onDelete(m)}
                      aria-label={`Delete stock ${isIn ? 'in' : 'out'} of ${formatKg(m.quantity_kg)}${m.product ? ` ${m.product}` : ''}`} />
            )}
          </li>
        )
      })}
    </ul>
  )
}
