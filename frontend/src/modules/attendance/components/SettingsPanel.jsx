import { Save } from 'lucide-react'
import { useState } from 'react'
import { attendanceApi } from '../../../api/attendanceApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Input, { Select } from '../../../components/common/Input'
import Loader from '../../../components/common/Loader'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import NoPermission from '../NoPermission'
import { clock, list } from '../shared'

/** Check-In window, office hours and the weekly holiday. Viewing needs View Settings; changing needs Modify Settings. */
export default function SettingsPanel({ options, onChanged }) {
  const toast = useToast()
  const canView = Boolean(options.data?.permissions?.settings_view || options.data?.permissions?.settings_manage)
  const settings = useApi(() => (canView ? attendanceApi.getSettings() : Promise.resolve(null)), [canView])
  const [draft, setDraft] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const canEdit = Boolean(options.data?.permissions?.settings_manage)
  const s = settings.data

  if (options.data && !canView) return <NoPermission what="Attendance settings" />
  if (settings.error && !s) return <ErrorMessage message={settings.error.message} onRetry={settings.reload} />
  if (!s) return <Loader label="Loading settings…" />

  const v = draft ?? { open_time: s.open_time, close_time: s.close_time, work_start: s.work_start, work_end: s.work_end, weekly_holiday: String(s.weekly_holiday) }
  const weekdays = list(options.data?.weekdays).map((d) => ({ value: String(d.value), label: d.label }))
  const weeklyLabel = weekdays.find((d) => d.value === v.weekly_holiday)?.label ?? s.weekly_holiday_label
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
          <Input label="Check-In Opens" type="time" value={v.open_time} disabled={!canEdit} error={error?.fields?.open_time?.[0]}
                 onChange={(e) => setDraft({ ...v, open_time: e.target.value })} />
          <Input label="Check-In Closes" type="time" value={v.close_time} disabled={!canEdit} error={error?.fields?.close_time?.[0]}
                 onChange={(e) => setDraft({ ...v, close_time: e.target.value })} />
          <Input label="Office Hours Start" type="time" value={v.work_start} disabled={!canEdit} error={error?.fields?.work_start?.[0]}
                 onChange={(e) => setDraft({ ...v, work_start: e.target.value })} />
          <Input label="Office Hours End" type="time" value={v.work_end} disabled={!canEdit} error={error?.fields?.work_end?.[0]}
                 onChange={(e) => setDraft({ ...v, work_end: e.target.value })} />
          <Select label="Weekly Holiday" value={v.weekly_holiday} disabled={!canEdit} error={error?.fields?.weekly_holiday?.[0]}
                  options={weekdays} onChange={(e) => setDraft({ ...v, weekly_holiday: e.target.value })} />
          <Input label="Timezone" value={s.timezone} disabled readOnly />
        </div>
        <div className="attendance-rule" aria-label="Current rule">
          <p><Badge tone="blue">OFFICE HOURS</Badge> {clock(v.work_start)} – {clock(v.work_end)}: the scheduled working hours; approved permission is deducted only inside them</p>
          <p><Badge tone="green">CHECK-IN OPEN</Badge> {clock(v.open_time)} → {clock(v.close_time)}{overnight ? ' next day' : ''}</p>
          <p><Badge tone="red">CHECK-IN CLOSED</Badge> {clock(v.close_time)} → {clock(v.open_time)}: check-out stays available for an open record until {clock(v.close_time)} the next morning</p>
          <p><Badge tone="gray">WEEKLY HOLIDAY</Badge> {weeklyLabel}: never counted as absent; office holidays are added in Calendar</p>
          <p className="muted">This automatically repeats every day. Nobody is checked out automatically. The server's clock (IST) decides; the browser's time is never used.</p>
        </div>
        {canEdit ? (
          <div><Button type="submit" icon={Save} loading={saving} disabled={!draft}>Save Settings</Button></div>
        ) : (
          <p className="muted">Only users with the Modify Settings permission can change these settings.</p>
        )}
      </form>
    </Card>
  )
}
