import { Plug } from 'lucide-react'
import { settingsApi } from '../../../api/settingsApi'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'
import EmptyState from '../../../components/common/EmptyState'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { useApi } from '../../../hooks/useApi'
import { formatDate } from '../../../utils/formatters'

/**
 * External services (e-mail, the AI engine) and whether they are connected. They are set up on the server
 * by the administrator, so this list only shows their status.
 */
export default function IntegrationsSection() {
  const items = useApi(() => settingsApi.getIntegrations(), [])
  const rows = Array.isArray(items.data) ? items.data : []

  return (
    <Card title="Integrations" subtitle="Services are connected on the server by the administrator; this shows whether each one is working">
      {items.loading && !items.data ? (
        <div className="skeleton skeleton--list" aria-label="Loading" />
      ) : items.error && !items.data ? (
        <ErrorMessage message={items.error.message} onRetry={items.reload} />
      ) : rows.length === 0 ? (
        <EmptyState compact icon={Plug} title="No integrations available" message="Available services appear here once they are enabled on the server." />
      ) : (
        <ul className="setting-list">
          {rows.map((it) => (
            <li key={it.key}>
              <div>
                <strong>{it.name}</strong>
                <span>
                  {it.description}
                  {it.connected && it.connected_at ? ` • connected ${formatDate(it.connected_at)}` : ''}
                </span>
              </div>
              <span className="setting-list__right">
                <Badge tone={it.connected ? 'green' : 'gray'}>{it.connected ? 'Connected' : 'Not connected'}</Badge>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
