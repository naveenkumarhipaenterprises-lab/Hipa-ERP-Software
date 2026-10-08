import { Clock, LogIn, LogOut } from 'lucide-react'
import { useEffect, useState } from 'react'
import { attendanceApi } from '../../../api/attendanceApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Loader from '../../../components/common/Loader'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { clock, day, list, whichDay } from '../shared'

const received = (data) => ({ ...data, receivedAt: Date.now() })

const IST_CLOCK = new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })

/**
 * The employee's own attendance. Open / closed, the times and the buttons all come from the server
 * (GET /attendance/status/); the clock only counts on from the server time between refreshes.
 */
export default function TodayPanel() {
  const toast = useToast()
  // Each status remembers when it arrived, so the clock can count on from the server time without trusting the browser clock
  const status = useApi(() => attendanceApi.getStatus().then(received), [])
  const [historyKey, setHistoryKey] = useState(0)
  const history = useApi(() => attendanceApi.listHistory({ page_size: 10 }), [historyKey])
  const [now, setNow] = useState(() => Date.now())
  const [busy, setBusy] = useState(false)
  const s = status.data
  const reload = status.reload

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000)
    const refresh = setInterval(reload, 60000) // the server re-decides open / closed every minute
    return () => {
      clearInterval(tick)
      clearInterval(refresh)
    }
  }, [reload])

  const act = async (kind) => {
    setBusy(true)
    try {
      const next = kind === 'in' ? await attendanceApi.checkIn() : await attendanceApi.checkOut()
      status.setData(received(next))
      setHistoryKey((k) => k + 1)
      toast.success(kind === 'in' ? `Checked in at ${clock(next.record?.check_in_at)}` : `Checked out at ${clock(next.record?.check_out_at)}`)
    } catch (err) {
      toast.error(err.message)
      status.reload()
    } finally {
      setBusy(false)
    }
  }

  if (status.error && !s) return <ErrorMessage message={status.error.message} onRetry={status.reload} />
  if (!s) return <Loader label="Loading attendance…" />

  const w = s.window
  const r = s.record
  const completed = Boolean(r?.check_out_at)
  const serverNow = s.server_time ? new Date(now + (Date.parse(s.server_time) - s.receivedAt)) : null

  return (
    <div className="stack">
      <Card>
        <div className="attendance-today">
          <div className="attendance-today__state">
            <span className={`attendance-dot attendance-dot--${w.is_open ? 'open' : 'closed'}`} aria-hidden />
            <div>
              <h2 className="attendance-today__title">{w.is_open ? 'Attendance Open' : 'Attendance Closed'}</h2>
              <p className="muted">{w.is_open ? `Closes ${whichDay(w.closes_at, s.server_time).toLowerCase()} at ${clock(w.closes_at)}` : w.message}</p>
            </div>
          </div>
          <dl className="attendance-facts">
            <div>
              <dt>Current server time</dt>
              <dd><Clock size={15} aria-hidden /> {serverNow ? `${IST_CLOCK.format(serverNow).toUpperCase()} IST` : '—'}</dd>
            </div>
            <div>
              <dt>Attendance window</dt>
              <dd>
                {w.is_open
                  ? `Opened ${whichDay(w.opens_at, s.server_time)} ${clock(w.opens_at)} · Closes ${whichDay(w.closes_at, s.server_time)} ${clock(w.closes_at)}`
                  : `Next opening: ${whichDay(w.opens_at, s.server_time)} ${clock(w.opens_at)}`}
              </dd>
            </div>
          </dl>
        </div>
      </Card>

      <Card title="Today's Attendance" subtitle={r ? `Attendance date ${day(r.attendance_date)}` : undefined}>
        {!s.employee ? (
          <p className="muted">Your login isn't linked to an employee yet. Ask an administrator to link it in Attendance → Employees.</p>
        ) : (
          <div className="attendance-today">
            <dl className="attendance-facts attendance-facts--row">
              <div><dt>Check-In</dt><dd className="attendance-time">{clock(r?.check_in_at)}</dd></div>
              <div><dt>Check-Out</dt><dd className="attendance-time">{clock(r?.check_out_at)}</dd></div>
              <div><dt>Working Duration</dt><dd className="attendance-time">{r?.duration ?? '—'}</dd></div>
              <div><dt>Status</dt><dd>{r ? <Badge tone={completed ? 'green' : r.status === 'Not checked out' ? 'red' : 'blue'}>{r.status}</Badge> : <Badge tone="amber">Not checked in</Badge>}</dd></div>
            </dl>
            <div className="attendance-actions">
              {!r && (
                <Button icon={LogIn} size="lg" onClick={() => act('in')} loading={busy} disabled={!s.can_check_in}>
                  Check In
                </Button>
              )}
              {r && !completed && (
                <Button icon={LogOut} size="lg" onClick={() => act('out')} loading={busy} disabled={!s.can_check_out}>
                  Check Out / Logout
                </Button>
              )}
              {!w.is_open && !completed && <small className="muted">Check-In and Check-Out are available while attendance is open.</small>}
              {w.is_open && !r && !s.permissions.check_in && <small className="muted">You don't have the Check-In permission.</small>}
              {w.is_open && r && !completed && !s.permissions.check_out && <small className="muted">You don't have the Check-Out permission.</small>}
            </div>
          </div>
        )}
      </Card>

      <Card title="Recent Attendance History" bodyClassName="card__body--flush">
        {history.error && !history.loading ? (
          <div className="card__pad"><ErrorMessage message={history.error.message} onRetry={history.reload} /></div>
        ) : (
          <Table
            loading={history.loading}
            caption="Recent attendance history"
            data={list(history.data?.results)}
            emptyTitle="No attendance records found."
            emptyMessage="Your check-ins appear here."
            columns={[
              { key: 'attendance_date', header: 'Date', render: (x) => <span className="nowrap">{day(x.attendance_date)}</span> },
              { key: 'check_in_at', header: 'Check-In', render: (x) => clock(x.check_in_at) },
              { key: 'check_out_at', header: 'Check-Out', render: (x) => clock(x.check_out_at) },
              { key: 'duration', header: 'Working Duration', render: (x) => x.duration ?? '—' },
              { key: 'status', header: 'Status', render: (x) => <Badge tone={x.check_out_at ? 'green' : x.status === 'Not checked out' ? 'red' : 'blue'}>{x.status}</Badge> },
            ]}
          />
        )}
      </Card>
    </div>
  )
}
