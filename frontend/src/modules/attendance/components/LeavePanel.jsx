import { CalendarClock, CircleCheck, Pencil, Plus, XCircle } from 'lucide-react'
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
import { clock, day, list } from '../shared'

const isPermission = (v) => v.type === 'permission'
const TONE = { Pending: 'amber', Approved: 'green', Rejected: 'red', Cancelled: 'red' }

function fields(o) {
  return [
    { name: 'type', label: 'Type', type: 'select', required: true, options: list(o.leave_types) },
    { name: 'date', label: 'Date', type: 'date', required: true },
    // A permission needs its times; a leave without times is a whole day
    { name: 'from_time', label: 'From Time', type: 'time', required: true, visible: isPermission },
    { name: 'to_time', label: 'To Time', type: 'time', required: true, visible: isPermission },
    { name: 'from_time', label: 'From Time (optional)', type: 'time', visible: (v) => !isPermission(v) },
    { name: 'to_time', label: 'To Time (optional)', type: 'time', visible: (v) => !isPermission(v) },
    { name: 'reason', label: 'Reason', required: true, full: true, placeholder: 'e.g. Personal work' },
    { name: 'remarks', label: 'Remarks', type: 'textarea', placeholder: 'Optional' },
  ]
}

/** Leave / Permission requests: own requests for everyone; all requests and approve / reject with permission. */
export default function LeavePanel({ options, refreshKey, onChanged }) {
  const toast = useToast()
  const o = options.data ?? {}
  const p = o.permissions ?? {}
  const [form, setForm] = useState(null) // { request? }
  const [confirm, setConfirm] = useState(null) // { request, action }
  const l = usePagedList(attendanceApi.listLeave, { scope: '', status: '', type: '' }, refreshKey)
  const allMode = l.filters.scope === 'all'

  const save = async (values) => {
    const body = { ...values, from_time: values.from_time || '', to_time: values.to_time || '' }
    if (form.request) await attendanceApi.updateLeave(form.request.id, body)
    else await attendanceApi.createLeave(body)
    toast.success(form.request ? 'Request updated' : 'Request submitted')
    onChanged()
  }
  const act = async () => {
    const r = await attendanceApi.leaveAction(confirm.request.id, confirm.action)
    toast.success(`${r.type} request ${r.status.toLowerCase()}`)
    onChanged()
  }

  const columns = [
    ...(allMode ? [{ key: 'employee', header: 'Employee', render: (r) => <strong>{r.employee.name}</strong> }] : []),
    { key: 'requested_at', header: 'Request Date', render: (r) => <span className="nowrap">{day(r.requested_at)}</span> },
    { key: 'type', header: 'Type', render: (r) => <Badge tone={r.type_value === 'leave' ? 'blue' : 'purple'}>{r.type}</Badge> },
    { key: 'date', header: 'Date', render: (r) => <span className="nowrap">{day(r.date)}</span> },
    { key: 'from_time', header: 'From', render: (r) => (r.from_time ? clock(r.from_time) : 'Whole day') },
    { key: 'to_time', header: 'To', render: (r) => (r.to_time ? clock(r.to_time) : '—') },
    { key: 'reason', header: 'Reason' },
    { key: 'status', header: 'Status', render: (r) => <Badge tone={TONE[r.status]}>{r.status}</Badge> },
    {
      key: 'actions', sticky: true, align: 'right', header: <span className="sr-only">Actions</span>,
      render: (r) => (
        <span className="row-actions">
          {r.can_approve && <Button size="sm" variant="soft" icon={CircleCheck} onClick={() => setConfirm({ request: r, action: 'approve' })} aria-label={`Approve ${r.employee.name} ${r.type} on ${day(r.date)}`}>Approve</Button>}
          {r.can_reject && <Button size="sm" variant="ghost" icon={XCircle} className="btn--tone-red" onClick={() => setConfirm({ request: r, action: 'reject' })} aria-label={`Reject ${r.employee.name} ${r.type} on ${day(r.date)}`}>Reject</Button>}
          {r.can_edit && <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setForm({ request: r })} aria-label={`Edit request for ${day(r.date)}`} />}
          {r.can_cancel && <Button size="sm" variant="ghost" icon={XCircle} onClick={() => setConfirm({ request: r, action: 'cancel' })} aria-label={`Cancel request for ${day(r.date)}`} />}
        </span>
      ),
    },
  ]

  const editing = form?.request
  const verb = { approve: 'Approve', reject: 'Reject', cancel: 'Cancel' }[confirm?.action]
  return (
    <Card title="Leave / Permission" subtitle={allMode ? "Every employee's requests" : 'Your requests'} bodyClassName="card__body--flush"
          action={p.leave_apply && <Button size="sm" icon={Plus} onClick={() => setForm({})}>New Request</Button>}>
      <ListToolbar
        search={l.search} onSearch={l.setSearch} searchLabel="Search reason or employee" onFilter={l.setFilter}
        filters={[
          ...(p.leave_view ? [{ name: 'scope', label: 'Whose requests', value: l.filters.scope,
                                options: [{ value: '', label: 'My requests' }, { value: 'all', label: 'All requests' }] }] : []),
          { name: 'type', label: 'Filter by type', value: l.filters.type, options: [{ value: '', label: 'All types' }, ...list(o.leave_types)] },
          { name: 'status', label: 'Filter by status', value: l.filters.status, options: [{ value: '', label: 'All statuses' }, ...list(o.leave_statuses)] },
        ]}
      />
      {l.result.error && !l.result.loading ? (
        <div className="card__pad"><ErrorMessage message={l.result.error.message} onRetry={l.result.reload} /></div>
      ) : (
        <Table
          loading={l.result.loading}
          caption="Leave and permission requests"
          data={l.rows}
          columns={columns}
          emptyIcon={CalendarClock}
          emptyTitle="No leave or permission requests found."
          emptyMessage={p.leave_apply ? 'Use New Request to ask for leave or permission.' : undefined}
          pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }}
        />
      )}
      <FormModal
        open={Boolean(form)}
        onClose={() => setForm(null)}
        title={editing ? 'Edit Request' : 'Leave / Permission Request'}
        fields={fields(o)}
        initialValues={editing ? { type: editing.type_value, date: editing.date, from_time: editing.from_time ?? '', to_time: editing.to_time ?? '',
                                    reason: editing.reason, remarks: editing.remarks ?? '' } : { type: 'leave' }}
        submitLabel={editing ? 'Save Changes' : 'Submit Request'}
        onSubmit={save}
      />
      <ConfirmDialog
        open={Boolean(confirm)}
        onClose={() => setConfirm(null)}
        onConfirm={act}
        danger={confirm?.action !== 'approve'}
        title={confirm ? `${verb} this request?` : ''}
        message={confirm && `${confirm.request.employee.name}: ${confirm.request.type} on ${day(confirm.request.date)}${confirm.request.from_time ? `, ${clock(confirm.request.from_time)} – ${clock(confirm.request.to_time)}` : ''}.`}
        confirmLabel={verb ?? 'Confirm'}
        cancelLabel="Back"
      />
    </Card>
  )
}
