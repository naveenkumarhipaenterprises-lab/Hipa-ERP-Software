import { Link2, Link2Off, Plug } from 'lucide-react'
import { useState } from 'react'
import { settingsApi } from '../../../api/settingsApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import EmptyState from '../../../components/common/EmptyState'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { formatDate } from '../../../utils/formatters'

/** External connections (payments, messaging, accounting…) listed by the API. */
export default function IntegrationsSection() {
  const toast = useToast()
  const items = useApi(() => settingsApi.getIntegrations(), [])
  const [busy, setBusy] = useState(null)
  const [disconnecting, setDisconnecting] = useState(null)
  const rows = Array.isArray(items.data) ? items.data : []

  const connect = async (it) => {
    setBusy(it.key)
    try {
      const res = await settingsApi.connectIntegration(it.key)
      // OAuth-style set-up continues on the provider's site
      if (typeof res?.redirect_url === 'string' && /^https:\/\//.test(res.redirect_url)) {
        window.location.assign(res.redirect_url)
        return
      }
      toast.success(`${it.name} connected`)
      items.reload()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(null)
    }
  }

  const disconnect = async () => {
    await settingsApi.disconnectIntegration(disconnecting.key)
    toast.success(`${disconnecting.name} disconnected`)
    items.reload()
  }

  return (
    <Card title="Integrations" subtitle="Connect the portal with external services">
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
                {it.connected ? (
                  <Button size="sm" variant="ghost" className="btn--tone-red" icon={Link2Off} onClick={() => setDisconnecting(it)}>
                    Disconnect
                  </Button>
                ) : (
                  <Button size="sm" variant="outline" icon={Link2} loading={busy === it.key} onClick={() => connect(it)}>
                    Connect
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={Boolean(disconnecting)}
        onClose={() => setDisconnecting(null)}
        onConfirm={disconnect}
        danger
        title={`Disconnect ${disconnecting?.name ?? ''}?`}
        message="Features that rely on this service will stop working until it is connected again."
        confirmLabel="Disconnect"
      />
    </Card>
  )
}
