import { CalendarClock } from 'lucide-react'
import EmptyState from '../../../components/common/EmptyState'
import { formatDate } from '../../../utils/formatters'

/** Upcoming activities from the API: [{ id, title, date, category? }] */
export default function UpcomingActivities({ items }) {
  if (!Array.isArray(items) || items.length === 0) {
    return <EmptyState compact icon={CalendarClock} title="No upcoming activities" message="Scheduled activities will appear here." />
  }
  return (
    <ul className="activity-list">
      {items.map((a, i) => {
        const d = new Date(a.date)
        const valid = !Number.isNaN(d.getTime())
        const [day, month] = valid ? formatDate(d).split(' ') : []
        return (
          <li key={a.id ?? i}>
            <time className="activity-list__date" dateTime={valid ? d.toISOString() : undefined}>
              {valid ? (
                <>
                  <strong>{day}</strong>
                  <span>{month}</span>
                </>
              ) : (
                <span>—</span>
              )}
            </time>
            <div className="activity-list__body">
              <p>{a.title}</p>
              <span>{[a.category, valid ? formatDate(d) : null].filter(Boolean).join(' • ')}</span>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
