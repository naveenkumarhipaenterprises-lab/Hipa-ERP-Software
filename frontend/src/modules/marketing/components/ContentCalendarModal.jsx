import { CalendarDays, Plus } from 'lucide-react'
import { marketingApi } from '../../../api/marketingApi'
import Button from '../../../components/common/Button'
import EmptyState from '../../../components/common/EmptyState'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import { useApi } from '../../../hooks/useApi'
import { formatDate } from '../../../utils/formatters'

/** Upcoming scheduled posts (GET /marketing/posts/?status=scheduled). */
export default function ContentCalendarModal({ open, onClose, onSchedule, refreshKey }) {
  if (!open) return null
  return <Calendar onClose={onClose} onSchedule={onSchedule} refreshKey={refreshKey} />
}

function Calendar({ onClose, onSchedule, refreshKey }) {
  const posts = useApi(() => marketingApi.listPosts({ status: 'scheduled', page_size: 20 }), [refreshKey])
  const rows = Array.isArray(posts.data?.results) ? posts.data.results : []

  return (
    <Modal
      open
      onClose={onClose}
      title="Content Calendar"
      subtitle="Upcoming scheduled posts"
      footer={
        onSchedule && (
          <Button icon={Plus} onClick={onSchedule}>
            Schedule Post
          </Button>
        )
      }
    >
      {posts.loading ? (
        <Loader label="Loading scheduled posts…" />
      ) : posts.error ? (
        <ErrorMessage message={posts.error.message} onRetry={posts.reload} />
      ) : rows.length === 0 ? (
        <EmptyState compact icon={CalendarDays} title="No posts scheduled" message="Scheduled posts will appear here in date order." />
      ) : (
        <ul className="activity-list">
          {rows.map((p) => {
            const [day, month] = p.scheduled_for ? formatDate(p.scheduled_for).split(' ') : ['—', '']
            return (
              <li key={p.id}>
                <time className="activity-list__date" dateTime={p.scheduled_for}>
                  <strong>{day}</strong>
                  <span>{month}</span>
                </time>
                <div className="activity-list__body">
                  <p>{p.caption}</p>
                  <span>{[p.platform, p.campaign].filter(Boolean).join(' • ')}</span>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Modal>
  )
}
