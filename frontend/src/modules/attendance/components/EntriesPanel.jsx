import { ClipboardPen, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { attendanceApi } from '../../../api/attendanceApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import ListToolbar from '../../../components/common/ListToolbar'
import Table from '../../../components/common/Table'
import { usePagedList } from '../../../hooks/usePagedList'
import { useToast } from '../../../hooks/useToast'
import { todayISO } from '../../../utils/formatters'
import NoPermission from '../NoPermission'
import { clock, day, list } from '../shared'

const hhmm = (iso) => (iso ? iso.slice(11, 16) : '')

/**
 * Manual Entries (Super Admin and Management): enter or correct someone's attendance when they forgot to check in or
 * out, or came late. Saving a day that already has a record corrects it. Every entry shows who made it and why.
 * Deleting a wrong record is for Super Admins only.
 */
export default function EntriesPanel({ options, refreshKey, onChanged }) {
  const toast = useToast()
  const o = options.data ?? {}
  const [form, setForm] = useState(null) // { record? }
  const [deleting, setDeleting] = useState(null)
  const l = usePagedList(attendanceApi.listRecords, { employee: '' }, refreshKey)
  if (options.data && !o.can_enter_attendance) return <NoPermission what="Enter attendance for others" />

  const employees = list(o.employees).map((e) => ({ value: String(e.id), label: `${e.employee_code} · ${e.name}` }))
  const fields = [
    { name: 'employee_id', label: 'Employee', type: 'select', required: true, options: employees, full: true },
    { name: 'date', label: 'Work date', type: 'date', required: true },
    { name: 'check_in', label: 'Check-in time', type: 'time', required: true },
    { name: 'check_out', label: 'Check-out time (leave empty if still working)', type: 'time' },
    { name: 'note', label: 'Reason', required: true, full: true, placeholder: 'e.g. Forgot to check in, came late, missed check-out' },
  ]
  const r = form?.record
  const initial = r
    ? { employee_id: String(r.employee.id), date: r.attendance_date, check_in: hhmm(r.check_in_at), check_out: hhmm(r.check_out_at), note: r.note ?? '' }
    : { date: todayISO() }

  const save = async (values) => {
    // A correction names its record, so changing the employee or work date moves it instead of adding a second one
    const saved = await attendanceApi.saveRecord({ ...values, check_out: values.check_out || null, ...(r ? { record_id: r.id } : {}) })
    toast.success(`Attendance saved for ${saved.employee.name}, ${day(saved.attendance_date)}`)
    onChanged()
  }
  const remove = async () => {
    await attendanceApi.deleteRecord(deleting.id)
    toast.success(`Attendance record deleted (${deleting.employee.name}, ${day(deleting.attendance_date)})`)
    onChanged()
  }

  return (
    <Card title="Manual Entries" subtitle="Enter or correct attendance for someone who forgot to check in or out, or came late"
          bodyClassName="card__body--flush"
          action={<Button size="sm" icon={Plus} onClick={() => setForm({})}>Add / Correct Entry</Button>}>
      <ListToolbar
        search={l.search} onSearch={l.setSearch} searchLabel="Search employee name or ID" onFilter={l.setFilter}
        filters={[{ name: 'employee', label: 'Filter by employee', value: l.filters.employee, options: [{ value: '', label: 'All employees' }, ...employees] }]}
      />
      {l.result.error && !l.result.loading ? (
        <div className="card__pad"><ErrorMessage message={l.result.error.message} onRetry={l.result.reload} /></div>
      ) : (
        <Table
          loading={l.result.loading}
          caption="Attendance records"
          data={l.rows}
          emptyIcon={ClipboardPen}
          emptyTitle="No attendance records"
          emptyMessage="Check-ins and manual entries will be listed here."
          pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }}
          columns={[
            { key: 'attendance_date', header: 'Work date', render: (x) => <span className="nowrap">{day(x.attendance_date)}</span> },
            { key: 'employee', header: 'Employee', render: (x) => <span><strong>{x.employee.name}</strong> <span className="muted">{x.employee.employee_code}</span></span> },
            { key: 'check_in_at', header: 'Check-in', render: (x) => clock(x.check_in_at) },
            { key: 'check_out_at', header: 'Check-out', render: (x) => clock(x.check_out_at) },
            { key: 'entered_by', header: 'Entered', render: (x) => (x.entered_by ? <Badge tone="amber">{`By ${x.entered_by}`}</Badge> : <Badge>Self</Badge>) },
            { key: 'note', header: 'Reason', render: (x) => x.note || '—' },
            {
              key: 'actions', sticky: true, align: 'right', header: <span className="sr-only">Actions</span>,
              render: (x) => (
                <span className="row-actions">
                  <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setForm({ record: x })} aria-label={`Correct ${x.employee.name} ${day(x.attendance_date)}`} />
                  {o.can_delete && (
                    <Button size="sm" variant="ghost" icon={Trash2} className="btn--tone-red" onClick={() => setDeleting(x)}
                            aria-label={`Delete ${x.employee.name} ${day(x.attendance_date)}`} />
                  )}
                </span>
              ),
            },
          ]}
        />
      )}

      <FormModal
        open={Boolean(form)}
        onClose={() => setForm(null)}
        title={r ? 'Correct attendance' : 'Add attendance entry'}
        subtitle="Times are IST. If the employee already has a record for that work date, it is corrected."
        submitLabel="Save Entry"
        fields={fields}
        initialValues={initial}
        onSubmit={save}
      />
      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        danger
        title="Delete this attendance record?"
        message={deleting && `${deleting.employee.name}'s attendance for ${day(deleting.attendance_date)} will be deleted.`}
        confirmLabel="Delete"
      />
    </Card>
  )
}
