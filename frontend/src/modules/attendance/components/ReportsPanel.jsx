import { Download, FileText } from 'lucide-react'
import { useState } from 'react'
import { attendanceApi } from '../../../api/attendanceApi'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Input, { Select } from '../../../components/common/Input'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import NoPermission from '../NoPermission'
import { day, list } from '../shared'

const FORMATS = [['pdf', 'PDF'], ['xlsx', 'Excel'], ['csv', 'CSV']]

function cell(value, format) {
  if (value === null || value === undefined || value === '') return '—'
  return format === 'date' ? day(String(value)) : value
}

/** Daily, Monthly, Employee and Leave / Permission reports from real records, with PDF / Excel / CSV export. */
export default function ReportsPanel({ options }) {
  const toast = useToast()
  const o = options.data ?? {}
  const [f, setF] = useState({ type: 'daily', date_from: '', date_to: '', employee: '', department: '', status: '' })
  const [downloading, setDownloading] = useState(null)
  const allowed = Boolean(o.permissions?.report_view)
  const needsEmployee = f.type === 'employee' && !f.employee
  const report = useApi(() => (allowed && !needsEmployee ? attendanceApi.getReport(f) : Promise.resolve(null)), [allowed, JSON.stringify(f)])

  if (options.data && !allowed) return <NoPermission what="Attendance reports" />

  const set = (name) => (e) => setF((x) => ({ ...x, [name]: e.target.value, ...(name === 'type' ? { status: '' } : {}) }))
  const statuses = f.type === 'leave' ? list(o.leave_statuses) : list(o.day_statuses)
  const download = async (format) => {
    setDownloading(format)
    try {
      await attendanceApi.downloadReport({ ...f, format })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setDownloading(null)
    }
  }
  const table = report.data?.table

  return (
    <Card
      title={report.data?.title ?? 'Reports'}
      bodyClassName="card__body--flush"
      action={
        <span className="row-actions">
          {FORMATS.map(([fmt, label]) => (
            <Button key={fmt} size="sm" variant="outline" icon={Download} loading={downloading === fmt}
                    disabled={needsEmployee || !table?.rows?.length} onClick={() => download(fmt)}>{label}</Button>
          ))}
        </span>
      }
    >
      <div className="toolbar">
        <Select className="field--inline" aria-label="Report" value={f.type} onChange={set('type')} options={list(o.report_types)} />
        <Input className="field--inline" type="date" aria-label="From date" value={f.date_from} onChange={set('date_from')} />
        <Input className="field--inline" type="date" aria-label="To date" value={f.date_to} onChange={set('date_to')} />
        <Select className="field--inline" aria-label="Employee" value={f.employee} onChange={set('employee')}
                options={[{ value: '', label: f.type === 'employee' ? 'Choose an employee' : 'All employees' },
                          ...list(o.employees).map((e) => ({ value: String(e.id), label: `${e.name} (${e.employee_code})` }))]} />
        <Select className="field--inline" aria-label="Department" value={f.department} onChange={set('department')}
                options={[{ value: '', label: 'All departments' }, ...list(o.departments).map((d) => ({ value: d, label: d }))]} />
        <Select className="field--inline" aria-label="Status" value={f.status} onChange={set('status')}
                options={[{ value: '', label: 'All statuses' }, ...statuses]} />
      </div>
      {needsEmployee ? (
        <p className="card__pad muted">Choose an employee for the Employee Attendance report.</p>
      ) : report.error && !report.loading ? (
        <div className="card__pad"><ErrorMessage message={report.error.message} onRetry={report.reload} /></div>
      ) : (
        <Table
          loading={report.loading}
          caption={report.data?.title ?? 'Attendance report'}
          data={list(table?.rows).map((r, i) => ({ id: i, ...r }))}
          columns={list(table?.columns).map((c) => ({ key: c.key, header: c.header, align: c.align, render: (r) => cell(r[c.key], c.format) }))}
          emptyIcon={FileText}
          emptyTitle="No report data available."
          emptyMessage="Try another date range or filter. Without dates the report covers this month so far."
        />
      )}
    </Card>
  )
}
