import { DatabaseBackup } from 'lucide-react'
import { useState } from 'react'
import { settingsApi } from '../../../api/settingsApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select, Toggle } from '../../../components/common/Input'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatTime } from '../../../utils/formatters'

/** Backup preferences and a manual "Back Up Now" (confirmed). */
export default function BackupSection({ options }) {
  const toast = useToast()
  const backup = useApi(() => settingsApi.getBackup(), [])
  const [confirming, setConfirming] = useState(false)
  const [saving, setSaving] = useState(false)
  const b = backup.data ?? {}
  const retention = Array.isArray(options.data?.backup_retention) ? options.data.backup_retention : []

  const update = async (changes, message) => {
    const before = backup.data
    backup.setData((d) => ({ ...d, ...changes }))
    setSaving(true)
    try {
      await settingsApi.updateBackup(changes)
      toast.success(message)
    } catch (err) {
      backup.setData(before)
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const runNow = async () => {
    const res = await settingsApi.runBackup()
    toast.success(res?.status ? `Backup ${String(res.status).toLowerCase()}` : 'Backup started')
    backup.reload()
  }

  return (
    <Card title="Data & Backup" subtitle="Protect your business data">
      {backup.loading && !backup.data ? (
        <div className="skeleton skeleton--list" aria-label="Loading" />
      ) : backup.error && !backup.data ? (
        <ErrorMessage message={backup.error.message} onRetry={backup.reload} />
      ) : (
        <ul className="setting-list">
          <li>
            <div>
              <strong>Automatic backup</strong>
              <span>Back up all business data every day</span>
            </div>
            <Toggle
              checked={Boolean(b.automatic)}
              disabled={saving}
              onChange={(on) => update({ automatic: on }, on ? 'Automatic backup turned on' : 'Automatic backup turned off')}
              label={<span className="sr-only">Automatic backup</span>}
            />
          </li>
          {retention.length > 0 && (
            <li>
              <div>
                <strong>Keep backups for</strong>
                <span>Older backups are deleted automatically</span>
              </div>
              <Select
                className="field--inline"
                aria-label="Backup retention"
                value={b.retention_months == null ? '' : String(b.retention_months)}
                disabled={saving}
                placeholder="Select…"
                onChange={(e) => update({ retention_months: Number(e.target.value) }, 'Backup retention updated')}
                options={retention.map((r) => ({ value: String(r.value), label: r.label }))}
              />
            </li>
          )}
          <li>
            <div>
              <strong>Last backup</strong>
              <span>{b.last_backup_at ? `${formatDate(b.last_backup_at)}, ${formatTime(b.last_backup_at)}` : 'No backup has been taken yet'}</span>
            </div>
            <span className="setting-list__right">
              {b.last_backup_status && <Badge>{b.last_backup_status}</Badge>}
              <Button size="sm" variant="outline" icon={DatabaseBackup} onClick={() => setConfirming(true)}>
                Back Up Now
              </Button>
            </span>
          </li>
        </ul>
      )}
      <ConfirmDialog
        open={confirming}
        onClose={() => setConfirming(false)}
        onConfirm={runNow}
        title="Start a backup now?"
        message="A full backup of business data will start on the server. The portal stays available while it runs."
        confirmLabel="Start Backup"
      />
    </Card>
  )
}
