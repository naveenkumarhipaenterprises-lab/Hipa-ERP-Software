import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Fragment, useState } from 'react'
import { attendanceApi } from '../../../api/attendanceApi'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select } from '../../../components/common/Input'
import Loader from '../../../components/common/Loader'
import { useApi } from '../../../hooks/useApi'
import { clock, day, list } from '../shared'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
// Present, Absent, Leave, Permission (no Holiday: the system has no holiday list)
const LEGEND = [['present', 'Present'], ['absent', 'Absent'], ['leave', 'Leave'], ['permission', 'Permission'], ['not_checked_out', 'Not checked out']]

function shift(month, by) {
  const [y, m] = month.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 1 + by, 1))
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`
}

/** Monthly calendar from real records (GET /attendance/calendar/). Own calendar; others with the calendar permission. */
export default function CalendarPanel({ options, refreshKey }) {
  const o = options.data ?? {}
  const [month, setMonth] = useState('') // empty: the server's current month
  const [employee, setEmployee] = useState('')
  const [selected, setSelected] = useState(null)
  const cal = useApi(() => attendanceApi.getCalendar({ month, employee }), [month, employee, refreshKey])
  const data = cal.data
  const shown = data?.month ?? month

  const byDate = Object.fromEntries(list(data?.days).map((d) => [d.date, d]))
  let cells = []
  if (shown) {
    const [y, m] = shown.split('-').map(Number)
    const first = new Date(Date.UTC(y, m - 1, 1)).getUTCDay() // 0 = Sunday
    const total = new Date(Date.UTC(y, m, 0)).getUTCDate()
    cells = [...Array((first + 6) % 7).fill(null), ...Array.from({ length: total }, (_, i) => `${shown}-${String(i + 1).padStart(2, '0')}`)]
  }
  const pick = selected && byDate[selected]

  return (
    <Card
      title="Calendar"
      subtitle={data?.employee ? `${data.employee.name} · ${data.employee.employee_code}` : undefined}
      action={
        <span className="row-actions">
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
      ) : !data.employee ? (
        <p className="muted">No attendance records found. Your login isn't linked to an employee yet.</p>
      ) : (
        <>
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
                        className={`attendance-calendar__cell ${selected === d ? 'attendance-calendar__cell--selected' : ''}`}
                        onClick={() => setSelected(d)}
                        aria-label={`${day(d)}: ${list(byDate[d]?.labels).join(', ') || 'No record'}`}>
                  <span className="attendance-calendar__num">{Number(d.slice(8))}</span>
                  <span className="attendance-calendar__chips">
                    {list(byDate[d]?.statuses).map((s) => <span key={s} className={`attendance-chip attendance-chip--${s}`} title={s} />)}
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
                  {pick.check_in_at && (<><dt>Check-In</dt><dd>{clock(pick.check_in_at)}</dd></>)}
                  {pick.check_in_at && (<><dt>Check-Out</dt><dd>{clock(pick.check_out_at)}</dd></>)}
                  {pick.duration && (<><dt>Working Duration</dt><dd>{pick.duration}</dd></>)}
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
        </>
      )}
    </Card>
  )
}
