import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])

/** Adds a post to the content calendar (POST /marketing/posts/). */
export default function SchedulePostModal({ open, options, onClose, onSchedule }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="Schedule Post" onClose={onClose}>
      {(data) => {
        if (list(data.platforms).length === 0) {
          return (
            <Modal open onClose={onClose} title="Schedule Post" size="sm">
              <EmptyState compact title="No marketing platforms set up" message="Connect at least one platform before scheduling posts. Contact your administrator." />
            </Modal>
          )
        }
        return (
          <FormModal
            open
            onClose={onClose}
            title="Schedule Post"
            subtitle="Add a post to the content calendar"
            submitLabel="Schedule Post"
            initialValues={{ scheduled_for: todayISO() }}
            fields={[
              { name: 'platform', label: 'Platform', type: 'select', required: true, options: list(data.platforms), placeholder: 'Select platform' },
              {
                name: 'scheduled_for',
                label: 'Publish date',
                type: 'date',
                required: true,
                validate: (v) => (v < todayISO() ? 'Choose today or a future date' : undefined),
              },
              { name: 'caption', label: 'Caption', type: 'textarea', required: true, placeholder: 'Write the post text' },
            ]}
            onSubmit={(values) => onSchedule({ ...values, caption: values.caption.trim() })}
          />
        )
      }}
    </OptionsGate>
  )
}
