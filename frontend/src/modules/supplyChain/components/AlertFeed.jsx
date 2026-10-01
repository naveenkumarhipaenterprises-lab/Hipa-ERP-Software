import { BellOff, CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react'
import EmptyState from '../../../components/common/EmptyState'

const ICONS = { error: CircleAlert, warning: TriangleAlert, success: CircleCheck, info: Info }

/** Supply chain alerts from the API: [{ id, type, title, detail? }] */
export default function AlertFeed({ items }) {
  const rows = Array.isArray(items) ? items : []
  if (rows.length === 0) {
    return <EmptyState compact icon={BellOff} title="No alerts" message="Delays, shortages and other supply alerts will appear here." />
  }
  return (
    <ul className="alert-feed">
      {rows.map((a, i) => {
        const type = ICONS[a.type] ? a.type : 'info'
        const Icon = ICONS[type]
        return (
          <li key={a.id ?? i} className={`alert-feed__item alert-feed__item--${type}`}>
            <Icon size={20} aria-hidden />
            <div>
              <p>{a.title}</p>
              {a.detail && <span>{a.detail}</span>}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
