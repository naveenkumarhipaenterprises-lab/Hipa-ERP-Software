import { CalendarOff, Clock, Eye, LogIn, UserCheck, UserX, Users } from 'lucide-react'
import { Fragment, useState } from 'react'
import { attendanceApi } from '../../../api/attendanceApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Input from '../../../components/common/Input'
import ListToolbar from '../../../components/common/ListToolbar'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import StatCard from '../../../components/dashboard/StatCard'
import { usePagedList } from '../../../hooks/usePagedList'
import { STATUS_TONES, clock, day, list } from '../shared'

const dash = (v) => v || '—'

function Statuses({ row }) {
  if (!row.statuses.length) return <span className="muted">—</span>
  return (
    <span className="row-actions">
      {row.statuses.map((s, i) => <Badge key={s} tone={STATUS_TONES[s]}>{row.labels[i]}</Badge>)}
    </span>
  )
}

/**
 * Everyone's attendance on one day (GET /attendance/dashboard/), for users with the View All permission:
 * summary counts and a filtered, searchable, paginated table. Every figure comes from the server.
 */
export default function AttendanceOverview({ options, refreshKey }) {
  const o = options.data ?? {}
  const [viewing, setViewing] = useState(null)
  const l = usePagedList(attendanceApi.getDashboard, { date: '', employee: '', department: '', status: '' }, refreshKey)
  const data = l.result.data
  const sum = data?.summary
  const loading = l.result.loading && !data

  return (
    <div className="stack">
      <div className="kpi-grid kpi-grid--auto" aria-label="Attendance summary">
        <StatCard icon={Users} tone="blue" label="Total Active Employees" value={sum?.total_active} loading={loading} />
        <StatCard icon={UserCheck} tone="green" label="Present" value={sum?.present} loading={loading} />
        <StatCard icon={UserX} tone="red" label="Absent" value={sum?.absent} loading={loading} />
        <StatCard icon={CalendarOff} tone="blue" label="On Approved Leave" value={sum?.on_leave} loading={loading} />
        <StatCard icon={Clock} tone="purple" label={data?.permission_label ?? 'Currently On Approved Permission'} value={sum?.on_permission} loading={loading} />
        <StatCard icon={LogIn} tone="orange" label="Checked In — Not Checked Out" value={sum?.not_checked_out} loading={loading} />
      </div>

      <Card
        title="Attendance Dashboard"
        subtitle={data ? `${day(data.date)}${data.holiday ? ` · ${data.holiday.label}: ${data.holiday.name}` : ''}` : undefined}
        bodyClassName="card__body--flush"
      >
        <ListToolbar
          search={l.search} onSearch={l.setSearch} searchLabel="Search name, employee ID or department" onFilter={l.setFilter}
          filters={[
            { name: 'employee', label: 'Filter by employee', value: l.filters.employee,
              options: [{ value: '', label: 'All employees' }, ...list(o.employees).map((e) => ({ value: String(e.id), label: `${e.name} (${e.employee_code})` }))] },
            { name: 'department', label: 'Filter by department', value: l.filters.department,
              options: [{ value: '', label: 'All departments' }, ...list(o.departments).map((d) => ({ value: d, label: d }))] },
            { name: 'status', label: 'Filter by status', value: l.filters.status, options: [{ value: '', label: 'All statuses' }, ...list(o.day_statuses)] },
          ]}
        />
        <div className="toolbar">
          <Input className="field--inline" type="date" aria-label="Date" value={l.filters.date} onChange={(e) => l.setFilter('date', e.target.value)} />
          {l.filters.date && <Button size="sm" variant="ghost" onClick={() => l.setFilter('date', '')}>Back to today</Button>}
        </div>
        {l.result.error && !l.result.loading ? (
          <div className="card__pad"><ErrorMessage message={l.result.error.message} onRetry={l.result.reload} /></div>
        ) : (
          <Table
            loading={l.result.loading}
            caption="Attendance dashboard"
            data={l.rows.map((r) => ({ id: r.employee.id, ...r }))}
            emptyIcon={Users}
            emptyTitle={l.filtered ? 'No employees match' : 'No active employees.'}
            emptyMessage={l.filtered ? 'Try another search, date or filter.' : 'Add employees in Attendance → Employees.'}
            pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }}
            columns={[
              { key: 'employee_code', header: 'Employee ID', render: (r) => <strong className="nowrap">{r.employee.employee_code}</strong> },
              { key: 'name', header: 'Name', render: (r) => r.employee.name },
              { key: 'department', header: 'Department', render: (r) => dash(r.employee.department) },
              { key: 'check_in_at', header: 'Check-In', render: (r) => clock(r.check_in_at) },
              { key: 'check_out_at', header: 'Check-Out', render: (r) => clock(r.check_out_at) },
              { key: 'working_duration', header: 'Working Hours', render: (r) => r.working_duration ?? '—' },
              { key: 'permission', header: 'Permission Time', render: (r) => list(r.permission_times).join(', ') || '—' },
              { key: 'status', header: 'Status', render: (r) => <Statuses row={r} /> },
              {
                key: 'actions', sticky: true, align: 'right', header: 'Action',
                render: (r) => <Button size="sm" variant="ghost" icon={Eye} onClick={() => setViewing(r)} aria-label={`View ${r.employee.name}`} />,
              },
            ]}
          />
        )}
      </Card>

      {viewing && (
        <Modal open onClose={() => setViewing(null)} title={viewing.employee.name} subtitle={`${viewing.employee.employee_code} · ${day(viewing.date)}`}>
          <dl className="detail-list">
            {[['Department', dash(viewing.employee.department)], ['Status', <Statuses key="s" row={viewing} />],
              ['Scheduled Working Hours', viewing.scheduled_duration ?? '—'], ['Actual Check-In', clock(viewing.check_in_at)],
              ['Actual Check-Out', clock(viewing.check_out_at)], ['Total Duration', viewing.total_duration ?? '—'],
              ['Approved Permission', list(viewing.permission_times).join(', ') || '—'],
              ['Approved Permission Duration', viewing.permission_duration ?? '—'], ['Actual Working Hours', viewing.working_duration ?? '—']]
              .map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd>{v}</dd></Fragment>)}
          </dl>
        </Modal>
      )}
    </div>
  )
}
