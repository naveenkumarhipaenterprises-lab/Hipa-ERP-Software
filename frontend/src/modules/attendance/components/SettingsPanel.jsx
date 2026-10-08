import { Save } from 'lucide-react'
import { useState } from 'react'
import { attendanceApi } from '../../../api/attendanceApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Input from '../../../components/common/Input'
import Loader from '../../../components/common/Loader'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { clock } from '../shared'

/** The attendance window. Everyone sees the rule; only users with the settings permission can change it. */
export default function SettingsPanel({ options, onChanged }) {
  const toast = useToast()
  const settings = useApi(() => attendanceApi.getSettings(), [])
  const [draft, setDraft] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const canEdit = Boolean(options.data?.permissions?.settings_manage)
  const s = settings.data

  if (settings.error && !s) return <ErrorMessage message={settings.error.message} onRetry={settings.reload} />
  if (!s) return <Loader label="Loading settings…" />

  const v = draft ?? { open_time: s.open_time, close_time: s.close_time, work_start: s.work_start, work_end: s.work_end }
  const overnight = v.close_time <= v.open_time
  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const next = await attendanceApi.updateSettings(v)
      settings.setData(next)
      setDraft(null)
      toast.success('Attendance settings saved')
      onChanged?.()
    } catch (err) {
      setError(err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card title="Attendance Settings">
      <form className="stack" onSubmit={save} noValidate>
        <ErrorMessage message={error?.message} />
        <div className="form-grid">
          <Input label="Attendance Open Time" type="time" value={v.open_time} disabled={!canEdit} error={error?.fields?.open_time?.[0]}
                 onChange={(e) => setDraft({ ...v, open_time: e.target.value })} />
          <Input label="Attendance Close Time" type="time" value={v.close_time} disabled={!canEdit} error={error?.fields?.close_time?.[0]}
                 onChange={(e) => setDraft({ ...v, close_time: e.target.value })} />
          <Input label="Working Hours Start" type="time" value={v.work_start} disabled={!canEdit} error={error?.fields?.work_start?.[0]}
                 onChange={(e) => setDraft({ ...v, work_start: e.target.value })} />
          <Input label="Working Hours End" type="time" value={v.work_end} disabled={!canEdit} error={error?.fields?.work_end?.[0]}
                 onChange={(e) => setDraft({ ...v, work_end: e.target.value })} />
          <Input label="Timezone" value={s.timezone} disabled readOnly />
        </div>
        <div className="attendance-rule" aria-label="Current rule">
          <p><Badge tone="blue">WORKING HOURS</Badge> {clock(v.work_start)} – {clock(v.work_end)}</p>
          <p><Badge tone="green">OPEN</Badge> {clock(v.open_time)} → {clock(v.close_time)}{overnight ? ' next day' : ''}: check-out for the day from {clock(v.open_time)}, check-in until {clock(v.close_time)}</p>
          <p><Badge tone="red">FROZEN</Badge> {clock(v.close_time)} → {clock(v.open_time)}: no check-in or check-out during working hours</p>
          <p className="muted">This automatically repeats every day. The server's clock (IST) decides; the browser's time is never used.</p>
        </div>
        {canEdit ? (
          <div><Button type="submit" icon={Save} loading={saving} disabled={!draft}>Save Settings</Button></div>
        ) : (
          <p className="muted">Only users with the Attendance Settings permission can change these times.</p>
        )}
      </form>
    </Card>
  )
}
