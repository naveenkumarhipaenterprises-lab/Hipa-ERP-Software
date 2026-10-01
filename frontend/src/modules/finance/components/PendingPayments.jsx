import { CircleCheck, Landmark, Package, Receipt, Users, Zap } from 'lucide-react'
import Badge from '../../../components/common/Badge'
import EmptyState from '../../../components/common/EmptyState'
import { formatDate, formatINR } from '../../../utils/formatters'

// Styling only: an icon per payment kind
const KIND_ICON = { supplier: Package, utility: Zap, salary: Users, tax: Landmark, other: Receipt }

/** Payments due, from the API: [{ id, party, kind?, due_date, amount, status }] */
export default function PendingPayments({ items }) {
  const rows = Array.isArray(items) ? items : []
  if (rows.length === 0) {
    return <EmptyState compact icon={CircleCheck} title="No pending payments" message="Bills and payables that are due will appear here." />
  }
  return (
    <ul className="payables">
      {rows.map((p, i) => {
        const Icon = KIND_ICON[p.kind] ?? Receipt
        return (
          <li key={p.id ?? i}>
            <Icon size={20} className="muted" aria-hidden />
            <span className="payables__who">
              <strong>{p.party}</strong>
              <small>{p.due_date ? `Due ${formatDate(p.due_date)}` : 'No due date'}</small>
            </span>
            <span className="payables__amt">
              <strong>{p.amount != null ? formatINR(p.amount) : '—'}</strong>
              {p.status && <Badge>{p.status}</Badge>}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
