import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])

/**
 * Creates (POST /marketing/campaigns/) or, with `campaign`, edits (PATCH /marketing/campaigns/<id>/) a campaign.
 * Platforms and objectives come from GET /marketing/options/.
 */
export default function CampaignFormModal({ open, options, campaign, onClose, onSave }) {
  if (!open) return null
  const title = campaign ? `Edit ${campaign.name}` : 'Create Campaign'
  return (
    <OptionsGate options={options} title={title} onClose={onClose}>
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
            title={title}
            subtitle={campaign ? 'Change the details of this campaign' : 'Launch a new marketing campaign'}
            submitLabel={campaign ? 'Save Changes' : 'Create Campaign'}
            initialValues={campaign ? {
              name: campaign.name, platform: campaign.platform_value, objective: campaign.objective, budget: campaign.budget,
              start_date: campaign.start_date, end_date: campaign.end_date, description: campaign.description ?? '',
            } : { start_date: todayISO() }}
            fields={fields}
            onSubmit={(values) => onSave({ ...values, name: values.name.trim(), description: values.description?.trim() ?? '' })}
          />
        )
      }}
    </OptionsGate>
  )
}
