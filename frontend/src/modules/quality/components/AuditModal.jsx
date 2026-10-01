import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])

/** Schedules a quality audit (POST /quality/audits/). Audit types come from GET /quality/options/. */
export default function AuditModal({ open, options, onClose, onSchedule }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="Schedule Audit" onClose={onClose}>
      {(data) => {
        if (list(data.audit_types).length === 0) {
          return (
            <Modal open onClose={onClose} title="Schedule Audit" size="sm">
              <EmptyState compact title="No audit types set up" message="Contact your administrator to add audit types." />
            </Modal>
          )
        }
        return (
          <FormModal
            open
            onClose={onClose}
            title="Schedule Audit"
            subtitle="Plan an internal or external quality audit"
            submitLabel="Schedule Audit"
            fields={[
              { name: 'audit_type', label: 'Audit type', type: 'select', required: true, options: data.audit_types, placeholder: 'Select type' },
              {
                name: 'date',
                label: 'Audit date',
                type: 'date',
                required: true,
                validate: (v) => (v < todayISO() ? 'Choose today or a future date' : undefined),
              },
              { name: 'auditor', label: 'Auditor / agency', full: true, placeholder: 'Who will carry out the audit' },
            ]}
            onSubmit={(values) => onSchedule({ ...values, auditor: values.auditor?.trim() || undefined })}
          />
        )
      }}
    </OptionsGate>
  )
}
