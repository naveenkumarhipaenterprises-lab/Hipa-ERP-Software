import { CalendarCheck, CircleCheck, XCircle } from 'lucide-react'
import { useState } from 'react'
import { qualityApi } from '../../../api/qualityApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import { Select } from '../../../components/common/Input'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { usePageReset } from '../../../hooks/usePageReset'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatNumber } from '../../../utils/formatters'

const PAGE_SIZE = 10
const FINDINGS_FIELDS = [{ name: 'findings', label: 'Findings', type: 'textarea', required: true, placeholder: 'What the auditor checked and found' }]

/** Scheduled, completed and cancelled audits; managers complete (with findings) or cancel scheduled ones. */
export default function AuditsTable({ refreshKey, statuses, canManage }) {
  const toast = useToast()
  const [status, setStatus] = useState('')
  const [completing, setCompleting] = useState(null)
  const [cancelling, setCancelling] = useState(null)
  const [page, setPage] = usePageReset(status)

  const audits = useApi(() => qualityApi.listAudits({ page, page_size: PAGE_SIZE, status }), [page, status, refreshKey])
  const rows = Array.isArray(audits.data?.results) ? audits.data.results : []
  const total = Number(audits.data?.count) || 0

  const complete = async (values) => {
    await qualityApi.setAuditStatus(completing.id, { status: 'completed', findings: values.findings.trim() })
    toast.success(`${completing.audit_type} on ${formatDate(completing.date)} completed`)
    audits.reload()
  }
  const cancel = async () => {
    await qualityApi.setAuditStatus(cancelling.id, { status: 'cancelled' })
    toast.success(`${cancelling.audit_type} on ${formatDate(cancelling.date)} cancelled`)
    audits.reload()
  }

  const columns = [
    { key: 'date', header: 'Date', render: (r) => <span className="nowrap">{r.date ? formatDate(r.date) : '—'}</span> },
    { key: 'audit_type', header: 'Audit', render: (r) => <strong>{r.audit_type}</strong> },
    { key: 'auditor', header: 'Auditor', render: (r) => r.auditor || '—' },
    { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
    { key: 'findings', header: 'Findings', render: (r) => r.findings || '—' },
  ]
  if (canManage) {
    columns.push({
      key: 'actions', sticky: true, align: 'right', header: <span className="sr-only">Actions</span>,
      render: (r) => r.can_update && (
        <span className="row-actions">
          <Button size="sm" variant="soft" icon={CircleCheck} onClick={() => setCompleting(r)} aria-label={`Complete ${r.audit_type} on ${formatDate(r.date)}`}>
            Complete
          </Button>
          <Button size="sm" variant="ghost" icon={XCircle} className="btn--tone-red" onClick={() => setCancelling(r)} aria-label={`Cancel ${r.audit_type} on ${formatDate(r.date)}`} />
        </span>
      ),
    })
  }

  return (
    <Card title="Audits" subtitle={audits.loading ? undefined : `${formatNumber(total)} audit${total === 1 ? '' : 's'}`} bodyClassName="card__body--flush">
      <div className="toolbar">
        <Select
          className="field--inline"
          aria-label="Filter audits by status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[{ value: '', label: 'All audits' }, ...(Array.isArray(statuses) ? statuses : [])]}
        />
      </div>
      {audits.error && !audits.loading ? (
        <div className="card__pad">
          <ErrorMessage message={audits.error.message} onRetry={audits.reload} />
        </div>
      ) : (
        <Table
          loading={audits.loading}
          caption="Quality audits"
          data={rows}
          columns={columns}
          emptyIcon={CalendarCheck}
          emptyTitle={status ? 'No audits with this status' : 'No audits yet'}
          emptyMessage={status ? 'Try another status.' : 'Scheduled audits appear here.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
        />
      )}
      <FormModal
        open={Boolean(completing)}
        onClose={() => setCompleting(null)}
        title={completing ? `Complete ${completing.audit_type}` : 'Complete audit'}
        subtitle={completing ? `${formatDate(completing.date)}${completing.auditor ? ` · ${completing.auditor}` : ''}` : undefined}
        fields={FINDINGS_FIELDS}
        submitLabel="Mark Completed"
        onSubmit={complete}
      />
      <ConfirmDialog
        open={Boolean(cancelling)}
        onClose={() => setCancelling(null)}
        onConfirm={cancel}
        danger
        title="Cancel this audit?"
        message={cancelling && `${cancelling.audit_type} on ${formatDate(cancelling.date)} will be cancelled. This cannot be undone.`}
        confirmLabel="Cancel Audit"
        cancelLabel="Keep Audit"
      />
    </Card>
  )
}
