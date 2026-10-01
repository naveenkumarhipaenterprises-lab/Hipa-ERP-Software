import { Inbox } from 'lucide-react'

/**
 * Shown wherever real data is not available yet. Never fill the gap with sample data.
 */
export default function EmptyState({ icon: Icon = Inbox, title = 'No data available', message, action, compact = false }) {
  return (
    <div className={`empty-state ${compact ? 'empty-state--compact' : ''}`} role="status">
      <div className="empty-state__icon" aria-hidden>
        <Icon size={compact ? 22 : 32} />
      </div>
      <h3 className="empty-state__title">{title}</h3>
      {message && <p className="empty-state__msg">{message}</p>}
      {action}
    </div>
  )
}
