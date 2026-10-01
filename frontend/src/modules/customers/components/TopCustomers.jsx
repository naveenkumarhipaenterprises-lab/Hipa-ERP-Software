import { Medal, Users } from 'lucide-react'
import EmptyState from '../../../components/common/EmptyState'
import { formatINR } from '../../../utils/formatters'

/** Ranked list of the highest-value customers from the API: [{ id, name, amount }] */
export default function TopCustomers({ items }) {
  const rows = Array.isArray(items) ? items : []
  if (rows.length === 0) {
    return <EmptyState compact icon={Users} title="No customer sales yet" message="Your highest-value customers will appear here." />
  }
  return (
    <ol className="rank-list">
      {rows.map((c, i) => (
        <li key={c.id ?? i}>
          {i < 3 ? (
            <Medal size={20} className={`rank-list__medal rank-list__medal--${i}`} aria-label={`Rank ${i + 1}`} />
          ) : (
            <span className="rank-list__num">{i + 1}</span>
          )}
          <span className="rank-list__name">{c.name}</span>
          <strong>{c.amount != null ? formatINR(c.amount) : '—'}</strong>
        </li>
      ))}
    </ol>
  )
}
