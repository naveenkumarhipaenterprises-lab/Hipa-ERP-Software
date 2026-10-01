import { Award } from 'lucide-react'
import Badge from '../../../components/common/Badge'
import EmptyState from '../../../components/common/EmptyState'
import { formatDate } from '../../../utils/formatters'

/** Certifications held, from the API: [{ id, name, detail?, valid_until?, status? }] */
export default function Certifications({ items }) {
  const rows = Array.isArray(items) ? items : []
  if (rows.length === 0) {
    return <EmptyState compact icon={Award} title="No certifications recorded" message="Food safety and quality certifications will be listed here." />
  }
  return (
    <ul className="cert-list">
      {rows.map((c, i) => (
        <li key={c.id ?? i} className="cert-list__item">
          <Award size={26} aria-hidden />
          <div>
            <strong>{c.name}</strong>
            {c.detail && <span>{c.detail}</span>}
            {c.valid_until && <small>Valid until {formatDate(c.valid_until)}</small>}
          </div>
          {c.status && <Badge>{c.status}</Badge>}
        </li>
      ))}
    </ul>
  )
}
