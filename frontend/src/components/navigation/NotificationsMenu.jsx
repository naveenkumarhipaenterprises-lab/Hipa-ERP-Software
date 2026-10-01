import { Bell, BellOff, CheckCheck, CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react'
import { useId, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { normalizeNotifications, notificationsApi } from '../../api/notificationsApi'
import { useApi } from '../../hooks/useApi'
import { useDismiss } from '../../hooks/useDismiss'
import { useToast } from '../../hooks/useToast'
import { formatRelativeTime } from '../../utils/formatters'
import ErrorMessage from '../common/ErrorMessage'

const TYPE_ICON = { warning: TriangleAlert, error: CircleAlert, success: CircleCheck, info: Info }

/** Bell button + panel. Everything shown comes from GET /notifications/; nothing is invented. */
export default function NotificationsMenu({ open, onToggle, onClose }) {
  const panelId = useId()
  const wrapRef = useRef(null)
  const buttonRef = useRef(null)
  const navigate = useNavigate()
  const toast = useToast()
  const { data, error, loading, reload, setData } = useApi(() => notificationsApi.list(), [])
  const { items, unread } = normalizeNotifications(data)

  useDismiss(wrapRef, open, onClose, buttonRef)

  const toggle = () => {
    if (!open) reload() // fetch the latest each time the panel opens
    onToggle()
  }

  const markRead = (ids) =>
    setData((d) => {
      const { items: list } = normalizeNotifications(d)
      const next = list.map((n) => (ids === 'all' || ids.includes(n.id) ? { ...n, read: true } : n))
      return Array.isArray(d) ? next : { ...d, results: next, unread_count: next.filter((n) => !n.read).length }
    })

  const markAllRead = async () => {
    const before = data
    markRead('all')
    try {
      await notificationsApi.markAllRead()
    } catch (err) {
      setData(before)
      toast.error(err.message)
    }
  }

  const openNote = (n) => {
    if (!n.read) {
      markRead([n.id])
      notificationsApi.markRead(n.id).catch(() => {
        /* the next reload shows the server's real state */
      })
    }
    if (typeof n.link === 'string' && n.link.startsWith('/') && !n.link.startsWith('//')) {
      onClose()
      navigate(n.link)
    }
  }

  const label = unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'

  return (
    <div className="dropdown" ref={wrapRef}>
      <button
        ref={buttonRef}
        className="icon-btn topbar__bell"
        onClick={toggle}
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
      >
        <Bell size={22} />
        {unread > 0 && (
          <span className="topbar__dot" aria-hidden>
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="dropdown__panel dropdown__panel--wide" id={panelId} role="region" aria-label="Notifications">
          <div className="dropdown__head">
            <p className="dropdown__title">Notifications</p>
            {unread > 0 && (
              <button className="link link--strong notes__mark" onClick={markAllRead}>
                <CheckCheck size={15} /> Mark all as read
              </button>
            )}
          </div>

          {loading && !data && !error && <p className="dropdown__empty">Loading notifications…</p>}
          {error && !loading && <ErrorMessage className="notes__error" message={error.message} onRetry={reload} />}
          {!loading && !error && items.length === 0 && (
            <div className="notes__empty">
              <BellOff size={22} aria-hidden />
              <span>You&apos;re all caught up. New alerts will appear here.</span>
            </div>
          )}

          {items.length > 0 && (
            <ul className="notes">
              {items.map((n) => {
                const Icon = TYPE_ICON[n.type] ?? Info
                return (
                  <li key={n.id}>
                    <button className={`note note--${n.type ?? 'info'} ${n.read ? '' : 'note--unread'}`} onClick={() => openNote(n)}>
                      <Icon size={18} aria-hidden />
                      <span className="note__body">
                        <strong>{n.title}</strong>
                        {n.message && <span className="note__msg">{n.message}</span>}
                        {n.created_at && (
                          <time dateTime={n.created_at} className="note__time">
                            {formatRelativeTime(n.created_at)}
                          </time>
                        )}
                      </span>
                      {!n.read && <span className="sr-only">(unread)</span>}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
