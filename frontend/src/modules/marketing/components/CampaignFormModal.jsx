import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])

/** Creates a campaign (POST /marketing/campaigns/). Platforms and objectives come from GET /marketing/options/. */
export default function CampaignFormModal({ open, options, onClose, onCreate }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="Create Campaign" onClose={onClose}>
      {(data) => {
        if (list(data.platforms).length === 0) {
          return (
            <Modal open onClose={onClose} title="Create Campaign" size="sm">
              <EmptyState compact title="No marketing platforms set up" message="Connect at least one platform before creating campaigns. Contact your administrator." />
            </Modal>
          )
        }
        const fields = [
          { name: 'name', label: 'Campaign name', required: true, full: true, placeholder: 'Enter a campaign name' },
          { name: 'platform', label: 'Platform', type: 'select', required: true, options: list(data.platforms), placeholder: 'Select platform' },
          { name: 'budget', label: 'Budget (₹)', type: 'number', required: true, min: 0, placeholder: 'Total budget in rupees' },
          { name: 'start_date', label: 'Start date', type: 'date', required: true },
          {
            name: 'end_date',
            label: 'End date',
            type: 'date',
            required: true,
            validate: (v, values) => (values.start_date && v < values.start_date ? 'End date cannot be before the start date' : undefined),
          },
          { name: 'description', label: 'Description', type: 'textarea', placeholder: 'Goal, audience and key message' },
        ]
        if (list(data.objectives).length) {
          fields.splice(2, 0, { name: 'objective', label: 'Objective', type: 'select', required: true, options: data.objectives, placeholder: 'Select objective' })
        }
        return (
          <FormModal
            open
            onClose={onClose}
            title="Create Campaign"
            subtitle="Launch a new marketing campaign"
            submitLabel="Create Campaign"
            initialValues={{ start_date: todayISO() }}
            fields={fields}
            onSubmit={(values) => onCreate({ ...values, name: values.name.trim(), description: values.description?.trim() || undefined })}
          />
        )
      }}
    </OptionsGate>
  )
}
