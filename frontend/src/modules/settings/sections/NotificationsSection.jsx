import { BellOff } from 'lucide-react'
import { settingsApi } from '../../../api/settingsApi'
import Card from '../../../components/common/Card'
import EmptyState from '../../../components/common/EmptyState'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Toggle } from '../../../components/common/Input'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'

/** Alert switches from the API; each change saves immediately and reverts if the server refuses. */
export default function NotificationsSection() {
  const toast = useToast()
  const prefs = useApi(() => settingsApi.getNotifications(), [])
  const rows = Array.isArray(prefs.data) ? prefs.data : []

  const toggle = async (key, enabled) => {
    const setEnabled = (on) => prefs.setData((list) => (Array.isArray(list) ? list.map((p) => (p.key === key ? { ...p, enabled: on } : p)) : list))
    setEnabled(enabled)
    try {
      await settingsApi.setNotification(key, enabled)
    } catch (err) {
      setEnabled(!enabled)
      toast.error(err.message)
    }
  }

  return (
    <Card title="Notification Settings" subtitle="Choose which alerts the team receives">
      {prefs.loading && !prefs.data ? (
        <div className="skeleton skeleton--list" aria-label="Loading" />
      ) : prefs.error && !prefs.data ? (
        <ErrorMessage message={prefs.error.message} onRetry={prefs.reload} />
      ) : rows.length === 0 ? (
        <EmptyState compact icon={BellOff} title="No notification types available" message="Alert types appear here once they are set up on the server." />
      ) : (
        <ul className="setting-list">
          {rows.map((p) => (
            <li key={p.key}>
              <div>
                <strong id={`notif-${p.key}`}>{p.title}</strong>
                {p.description && <span>{p.description}</span>}
              </div>
              <Toggle checked={Boolean(p.enabled)} onChange={(on) => toggle(p.key, on)} label={<span className="sr-only">{p.title}</span>} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
