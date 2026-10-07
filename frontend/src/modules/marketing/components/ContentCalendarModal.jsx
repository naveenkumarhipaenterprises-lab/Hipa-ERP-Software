import { CalendarDays, CircleCheck, Plus, XCircle } from 'lucide-react'
import { useState } from 'react'
import { marketingApi } from '../../../api/marketingApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import EmptyState from '../../../components/common/EmptyState'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { formatDate } from '../../../utils/formatters'

/**
 * Scheduled posts (GET /marketing/posts/?status=scheduled), including ones whose time has come ("Due").
 * There is no Instagram/Facebook connection: staff post by hand, then mark the post published here.
 */
export default function ContentCalendarModal({ open, onClose, onSchedule, refreshKey, canManage }) {
  if (!open) return null
  return <Calendar onClose={onClose} onSchedule={onSchedule} refreshKey={refreshKey} canManage={canManage} />
}

function Calendar({ onClose, onSchedule, refreshKey, canManage }) {
  const toast = useToast()
  const [change, setChange] = useState(null) // { post, status }
  const posts = useApi(() => marketingApi.listPosts({ status: 'scheduled', page_size: 20 }), [refreshKey])
  const rows = Array.isArray(posts.data?.results) ? posts.data.results : []

  const update = async () => {
    await marketingApi.setPostStatus(change.post.id, change.status)
    toast.success(change.status === 'published' ? 'Post marked published' : 'Post cancelled')
    posts.reload()
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Content Calendar"
      subtitle="Scheduled posts. Post them on the platform, then mark them published."
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
                  {p.is_due && <Badge tone="amber">Due</Badge>}
                </div>
                {canManage && p.can_update && (
                  <span className="row-actions">
                    <Button size="sm" variant="soft" icon={CircleCheck} onClick={() => setChange({ post: p, status: 'published' })} aria-label={`Mark the ${p.platform} post published`}>
                      Published
                    </Button>
                    <Button size="sm" variant="ghost" icon={XCircle} className="btn--tone-red" onClick={() => setChange({ post: p, status: 'cancelled' })} aria-label={`Cancel the ${p.platform} post`} />
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}
      <ConfirmDialog
        open={Boolean(change)}
        onClose={() => setChange(null)}
        onConfirm={update}
        danger={change?.status === 'cancelled'}
        title={change?.status === 'published' ? 'Mark this post published?' : 'Cancel this post?'}
        message={change && (change.status === 'published'
          ? `Confirm it is posted on ${change.post.platform}. This app doesn't post it for you.`
          : 'It will be removed from the calendar. This cannot be undone.')}
        confirmLabel={change?.status === 'published' ? 'Mark Published' : 'Cancel Post'}
        cancelLabel="Back"
      />
    </Modal>
  )
}
