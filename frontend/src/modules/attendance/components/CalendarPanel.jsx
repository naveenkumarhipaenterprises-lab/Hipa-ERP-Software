import { ChevronLeft, ChevronRight, Pencil, Plus, Trash2 } from 'lucide-react'
import { Fragment, useState } from 'react'
import { attendanceApi } from '../../../api/attendanceApi'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import { Select } from '../../../components/common/Input'
import Loader from '../../../components/common/Loader'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { clock, day, list } from '../shared'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const LEGEND = [['present', 'Present'], ['absent', 'Absent'], ['leave', 'On Leave'], ['permission', 'On Permission'],
  ['not_checked_out', 'Not checked out'], ['office_holiday', 'Office Holiday'], ['weekly_holiday', 'Weekly Holiday']]
const HOLIDAY_FIELDS = [
  { name: 'name', label: 'Holiday Name', required: true },
  { name: 'date', label: 'Date', type: 'date', required: true },
  { name: 'description', label: 'Description', type: 'textarea' },
]

function shift(month, by) {
  const [y, m] = month.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 1 + by, 1))
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`
}

/**
 * Monthly calendar from real records (GET /attendance/calendar/). Own calendar; others with the calendar permission.
 * Weekly and office holidays are shown for everyone; office holidays are added / edited / deleted here (holiday permission).
 */
export default function CalendarPanel({ options, refreshKey, onChanged }) {
  const toast = useToast()
  const o = options.data ?? {}
  const [month, setMonth] = useState('') // empty: the server's current month
  const [employee, setEmployee] = useState('')
  const [selected, setSelected] = useState(null)
  const [holidayForm, setHolidayForm] = useState(null) // { holiday? }
  const [deleting, setDeleting] = useState(null)
  const cal = useApi(() => attendanceApi.getCalendar({ month, employee }), [month, employee, refreshKey])
  const data = cal.data
  const shown = data?.month ?? month
  const canManage = Boolean(o.permissions?.holiday_manage)

  const byDate = Object.fromEntries(list(data?.days).map((d) => [d.date, d]))
  let cells = []
  if (shown) {
    const [y, m] = shown.split('-').map(Number)
    const first = new Date(Date.UTC(y, m - 1, 1)).getUTCDay() // 0 = Sunday
    const total = new Date(Date.UTC(y, m, 0)).getUTCDate()
    cells = [...Array((first + 6) % 7).fill(null), ...Array.from({ length: total }, (_, i) => `${shown}-${String(i + 1).padStart(2, '0')}`)]
  }
  const pick = selected && byDate[selected]
  const holidays = list(data?.holidays)

  const saveHoliday = async (values) => {
    const h = holidayForm.holiday
      ? await attendanceApi.updateHoliday(holidayForm.holiday.id, values)
      : await attendanceApi.createHoliday(values)
    toast.success(holidayForm.holiday ? `${h.name} updated` : `${h.name} added`)
    onChanged?.()
  }
  const removeHoliday = async () => {
    await attendanceApi.deleteHoliday(deleting.id)
    toast.success(`${deleting.name} deleted`)
    onChanged?.()
  }

  return (
    <Card
      title="Calendar"
      subtitle={data?.employee ? `${data.employee.name} · ${data.employee.employee_code}` : undefined}
      action={
        <span className="row-actions">
          {canManage && <Button size="sm" icon={Plus} onClick={() => setHolidayForm({})}>Add Office Holiday</Button>}
          {o.permissions?.calendar_view && (
            <Select className="field--inline" aria-label="Employee" value={employee} onChange={(e) => { setEmployee(e.target.value); setSelected(null) }}
                    options={[{ value: '', label: 'My calendar' }, ...list(o.employees).map((e) => ({ value: String(e.id), label: `${e.name} (${e.employee_code})` }))]} />
          )}
          <Button size="sm" variant="ghost" icon={ChevronLeft} aria-label="Previous month" disabled={!shown} onClick={() => { setMonth(shift(shown, -1)); setSelected(null) }} />
          <strong className="nowrap">{shown ? `${MONTH_NAMES[Number(shown.slice(5)) - 1]} ${shown.slice(0, 4)}` : ''}</strong>
          <Button size="sm" variant="ghost" icon={ChevronRight} aria-label="Next month" disabled={!shown} onClick={() => { setMonth(shift(shown, 1)); setSelected(null) }} />
        </span>
      }
    >
      {cal.error && !cal.loading ? (
        <ErrorMessage message={cal.error.message} onRetry={cal.reload} />
      ) : !data ? (
        <Loader label="Loading calendar…" />
      ) : (
        <>
          {!data.employee && <p className="muted">Your login isn't linked to an employee yet, so only holidays are shown.</p>}
          <ul className="attendance-legend" aria-label="Legend">
            {LEGEND.map(([k, label]) => <li key={k}><span className={`attendance-chip attendance-chip--${k}`} aria-hidden />{label}</li>)}
          </ul>
          <div className="attendance-calendar" aria-label="Attendance calendar">
            {WEEKDAYS.map((w) => <div key={w} className="attendance-calendar__head">{w}</div>)}
            {cells.map((d, i) =>
              d === null ? (
                <div key={`blank-${i}`} className="attendance-calendar__cell attendance-calendar__cell--blank" aria-hidden />
              ) : (
                <button key={d} type="button" aria-pressed={selected === d}
                        className={`attendance-calendar__cell ${byDate[d]?.holiday ? 'attendance-calendar__cell--holiday' : ''} ${selected === d ? 'attendance-calendar__cell--selected' : ''}`}
                        onClick={() => setSelected(d)}
                        aria-label={`${day(d)}: ${list(byDate[d]?.labels).join(', ') || 'No record'}`}>
                  <span className="attendance-calendar__num">{Number(d.slice(8))}</span>
                  <span className="attendance-calendar__chips">
                    {list(byDate[d]?.statuses).map((s, j) => <span key={s} className={`attendance-chip attendance-chip--${s}`} title={byDate[d].labels[j]} />)}
                  </span>
                </button>
              ),
            )}
          </div>
          {selected && (
            <div className="attendance-day">
              <h3 className="modal__section-title">{day(selected)}</h3>
              {!pick || pick.statuses.length === 0 ? (
                <p className="muted">No attendance records found for this day.</p>
              ) : (
                <dl className="detail-list">
                  <dt>Status</dt><dd>{pick.labels.join(', ')}</dd>
                  {pick.holiday && (<><dt>{pick.holiday.label}</dt><dd>{pick.holiday.name}{pick.holiday.description ? ` · ${pick.holiday.description}` : ''}</dd></>)}
                  {pick.scheduled_duration && (<><dt>Scheduled Working Hours</dt><dd>{pick.scheduled_duration}</dd></>)}
                  {pick.check_in_at && (<><dt>Actual Check-In</dt><dd>{clock(pick.check_in_at)}</dd></>)}
                  {pick.check_in_at && (<><dt>Actual Check-Out</dt><dd>{clock(pick.check_out_at)}</dd></>)}
                  {pick.total_duration && (<><dt>Total Duration</dt><dd>{pick.total_duration}</dd></>)}
                  {pick.total_duration && (<><dt>Approved Permission Duration</dt><dd>{pick.permission_duration}</dd></>)}
                  {pick.working_duration && (<><dt>Actual Working Hours</dt><dd>{pick.working_duration}</dd></>)}
                  {pick.leaves.map((lv, i) => (
                    <Fragment key={i}>
                      <dt>{lv.type}</dt>
                      <dd>{lv.from_time ? `${clock(lv.from_time)} – ${clock(lv.to_time)} · ` : 'Whole day · '}{lv.reason}</dd>
                    </Fragment>
                  ))}
                </dl>
              )}
            </div>
          )}
          <div className="attendance-day">
            <h3 className="modal__section-title">Office holidays this month</h3>
            {holidays.length === 0 ? (
              <p className="muted">No office holidays this month.</p>
            ) : (
              <ul className="attendance-holidays">
                {holidays.map((h) => (
                  <li key={h.id}>
                    <span><strong>{day(h.date)}</strong> · {h.weekday} · {h.name}{h.description ? <span className="muted"> — {h.description}</span> : null}</span>
                    {canManage && (
                      <span className="row-actions">
                        <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setHolidayForm({ holiday: h })} aria-label={`Edit ${h.name}`} />
                        <Button size="sm" variant="ghost" icon={Trash2} className="btn--tone-red" onClick={() => setDeleting(h)} aria-label={`Delete ${h.name}`} />
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}

      <FormModal
        open={Boolean(holidayForm)}
        onClose={() => setHolidayForm(null)}
        title={holidayForm?.holiday ? `Edit ${holidayForm.holiday.name}` : 'Add Office Holiday'}
        fields={HOLIDAY_FIELDS}
        initialValues={holidayForm?.holiday
          ? { name: holidayForm.holiday.name, date: holidayForm.holiday.date, description: holidayForm.holiday.description ?? '' }
          : { date: selected ?? '' }}
        submitLabel="Save"
        onSubmit={saveHoliday}
      />
      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={removeHoliday}
        danger
        title="Delete office holiday?"
        message={deleting ? `Are you sure you want to delete ${deleting.name} (${day(deleting.date)})? That day becomes a working day again.` : ''}
        confirmLabel="Delete"
        cancelLabel="Keep"
      />
    </Card>
  )
}
