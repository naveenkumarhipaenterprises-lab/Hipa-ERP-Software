import { FlaskConical } from 'lucide-react'
import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])

/** Records lab results for a batch waiting to be tested (POST /quality/tests/). */
export default function TestEntryModal({ open, options, onClose, onSave }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="New Test Entry" onClose={onClose} loadingLabel="Loading batches…">
      {(data) => {
        const batches = list(data.pending_batches).map((b) => ({
          value: String(b.id),
          label: b.product ? `${b.batch_number} • ${b.product}` : b.batch_number,
        }))
        if (batches.length === 0 || list(data.results).length === 0) {
          return (
            <Modal open onClose={onClose} title="New Test Entry" size="sm">
              <EmptyState
                compact
                icon={FlaskConical}
                title={batches.length === 0 ? 'No batches waiting for testing' : 'Test results are not set up'}
                message={batches.length === 0 ? 'Batches appear here once production sends them for quality testing.' : 'Contact your administrator.'}
              />
            </Modal>
          )
        }
        return (
          <FormModal
            open
            onClose={onClose}
            title="New Test Entry"
            subtitle="Record lab results for a batch"
            submitLabel="Save Result"
            initialValues={{ test_date: todayISO() }}
            fields={[
              { name: 'batch_id', label: 'Batch', type: 'select', required: true, options: batches, placeholder: 'Select batch', full: true },
              {
                name: 'test_date',
                label: 'Test date',
                type: 'date',
                required: true,
                validate: (v) => (v > todayISO() ? 'Test date cannot be in the future' : undefined),
              },
              { name: 'result', label: 'Result', type: 'select', required: true, options: data.results, placeholder: 'Select result' },
              { name: 'parameters', label: 'Parameters tested', required: true, full: true, placeholder: 'List the parameters checked' },
              { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'Readings, observations or reasons for failure' },
            ]}
            onSubmit={(values) => onSave({ ...values, parameters: values.parameters.trim(), notes: values.notes?.trim() || undefined })}
          />
        )
      }}
    </OptionsGate>
  )
}
