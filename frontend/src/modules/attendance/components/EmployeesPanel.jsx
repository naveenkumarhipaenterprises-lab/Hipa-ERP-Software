import { Eye, Pencil, Plus, Trash2, Users } from 'lucide-react'
import { Fragment, useState } from 'react'
import { attendanceApi } from '../../../api/attendanceApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import ListToolbar from '../../../components/common/ListToolbar'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { usePagedList } from '../../../hooks/usePagedList'
import { useToast } from '../../../hooks/useToast'
import NoPermission from '../NoPermission'
import { day, list } from '../shared'

const dash = (v) => v || '—'

function fields(o, editing) {
  const users = list(o.users).map((u) => ({ value: String(u.id), label: `${u.name} (${u.email})` }))
  if (editing?.user && !users.some((u) => u.value === String(editing.user.id))) {
    users.unshift({ value: String(editing.user.id), label: `${editing.user.name} (${editing.user.email})` })
  }
  return [
    { name: 'employee_code', label: 'Employee ID', required: true },
    { name: 'name', label: 'Employee Name', required: true },
    { name: 'department', label: 'Department' },
    { name: 'designation', label: 'Designation' },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'phone', label: 'Phone', type: 'tel' },
    { name: 'joining_date', label: 'Joining Date', type: 'date' },
    { name: 'status', label: 'Status', type: 'select', required: true, options: list(o.employee_statuses) },
    { name: 'user_id', label: 'Portal login (to mark own attendance)', type: 'select', full: true, placeholder: 'Not linked', options: users },
  ]
}

/** Employees (Attendance → Employees). Deleting removes the employee from the list; their attendance history is kept. */
export default function EmployeesPanel({ options, refreshKey, onChanged }) {
  const toast = useToast()
  const o = options.data ?? {}
  const [form, setForm] = useState(null) // { employee? }
  const [viewing, setViewing] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const l = usePagedList(attendanceApi.listEmployees, { status: '', department: '' }, refreshKey)

  if (options.data && !o.permissions?.employee_manage) return <NoPermission what="Manage employees" />

  const save = async (values) => {
    const body = { ...values, user_id: values.user_id || null }
    const e = form.employee ? await attendanceApi.updateEmployee(form.employee.id, body) : await attendanceApi.createEmployee(body)
    toast.success(form.employee ? `${e.name} updated` : `${e.name} added`)
    onChanged()
  }
  const remove = async () => {
    await attendanceApi.deleteEmployee(deleting.id)
    toast.success(`${deleting.name} deleted`)
    onChanged()
  }

  const editing = form?.employee
  return (
    <Card title="Employees" subtitle="Employee list" bodyClassName="card__body--flush"
          action={<Button size="sm" icon={Plus} onClick={() => setForm({})}>Add Employee</Button>}>
      <ListToolbar
        search={l.search} onSearch={l.setSearch} searchLabel="Search name, employee ID, department or email" onFilter={l.setFilter}
        filters={[
          { name: 'status', label: 'Filter by status', value: l.filters.status, options: [{ value: '', label: 'All statuses' }, ...list(o.employee_statuses)] },
          { name: 'department', label: 'Filter by department', value: l.filters.department,
            options: [{ value: '', label: 'All departments' }, ...list(o.departments).map((d) => ({ value: d, label: d }))] },
        ]}
      />
      {l.result.error && !l.result.loading ? (
        <div className="card__pad"><ErrorMessage message={l.result.error.message} onRetry={l.result.reload} /></div>
      ) : (
        <Table
          loading={l.result.loading}
          caption="Employees"
          data={l.rows}
          emptyIcon={Users}
          emptyTitle={l.filtered ? 'No employees match' : 'No employees found.'}
          emptyMessage={l.filtered ? 'Try another search or filter.' : 'Add your first employee to start keeping attendance.'}
          pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }}
          columns={[
            { key: 'employee_code', header: 'Employee ID', render: (e) => <strong className="nowrap">{e.employee_code}</strong> },
            { key: 'name', header: 'Employee Name' },
            { key: 'department', header: 'Department', render: (e) => dash(e.department) },
            { key: 'designation', header: 'Designation', render: (e) => dash(e.designation) },
            { key: 'phone', header: 'Phone', render: (e) => dash(e.phone) },
            { key: 'status', header: 'Status', render: (e) => <Badge>{e.status}</Badge> },
            {
              key: 'actions', sticky: true, align: 'right', header: <span className="sr-only">Actions</span>,
              render: (e) => (
                <span className="row-actions">
                  <Button size="sm" variant="ghost" icon={Eye} onClick={() => setViewing(e)} aria-label={`View ${e.name}`} />
                  <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setForm({ employee: e })} aria-label={`Edit ${e.name}`} />
                  <Button size="sm" variant="ghost" icon={Trash2} className="btn--tone-red" onClick={() => setDeleting(e)} aria-label={`Delete ${e.name}`} />
                </span>
              ),
            },
          ]}
        />
      )}

      <FormModal
        open={Boolean(form)}
        onClose={() => setForm(null)}
        title={editing ? `Edit ${editing.name}` : 'Add Employee'}
        fields={fields(o, editing)}
        initialValues={editing ? {
          employee_code: editing.employee_code, name: editing.name, department: editing.department ?? '', designation: editing.designation ?? '',
          email: editing.email ?? '', phone: editing.phone ?? '', joining_date: editing.joining_date ?? '', status: editing.status_value,
          user_id: editing.user ? String(editing.user.id) : '',
        } : { status: 'active' }}
        submitLabel={editing ? 'Save Changes' : 'Add Employee'}
        onSubmit={save}
      />
      {viewing && (
        <Modal open onClose={() => setViewing(null)} title={viewing.name} subtitle={viewing.employee_code}>
          <dl className="detail-list">
            {[['Employee ID', viewing.employee_code], ['Employee Name', viewing.name], ['Department', dash(viewing.department)],
              ['Designation', dash(viewing.designation)], ['Email', dash(viewing.email)], ['Phone', dash(viewing.phone)],
              ['Joining Date', viewing.joining_date ? day(viewing.joining_date) : '—'], ['Status', <Badge key="s">{viewing.status}</Badge>],
              ['Portal login', viewing.user ? `${viewing.user.name} (${viewing.user.email})` : 'Not linked']].map(([k, v]) => (
              <Fragment key={k}><dt>{k}</dt><dd>{v}</dd></Fragment>
            ))}
          </dl>
        </Modal>
      )}
      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        danger
        title="Delete employee?"
        message="Are you sure you want to delete this employee?"
        confirmLabel="Delete"
        cancelLabel="Keep"
      />
    </Card>
  )
}
