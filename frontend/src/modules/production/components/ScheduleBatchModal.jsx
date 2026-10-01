import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { formatKg, todayISO } from '../../../utils/formatters'

const toOptions = (items) => (Array.isArray(items) ? items : []).map((x) => ({ value: String(x.id), label: x.name }))

/**
 * Schedules a production batch (POST /production/batches/).
 * Opened from a plan row, the product and the plan's recommended quantity are pre-filled.
 */
export default function ScheduleBatchModal({ open, planRow, options, onClose, onSchedule }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="Schedule Batch" onClose={onClose} loadingLabel="Loading products and lines…">
      {(data) => {
        const products = toOptions(data.products)
        const lines = toOptions(data.lines)
        if (products.length === 0 || lines.length === 0) {
          return (
            <Modal open onClose={onClose} title="Schedule Batch" size="sm">
              <EmptyState
                compact
                title={products.length === 0 ? 'No products set up' : 'No production lines set up'}
                message="Production batches need products and production lines. Contact your administrator."
              />
            </Modal>
          )
        }

        const hints = planRow
          ? [
              planRow.recommended_kg != null && `recommended ${formatKg(planRow.recommended_kg)}`,
              planRow.capacity_kg != null && `capacity ${formatKg(planRow.capacity_kg)}`,
            ].filter(Boolean)
          : []

        return (
          <FormModal
            open
            onClose={onClose}
            title={planRow ? `Schedule batch: ${planRow.product}` : 'Schedule Batch'}
            subtitle={hints.length ? `From the production plan: ${hints.join(' • ')}` : 'Plan a new production batch'}
            submitLabel="Schedule Batch"
            initialValues={{
              product_id: planRow?.product_id != null ? String(planRow.product_id) : '',
              quantity_kg: planRow?.recommended_kg > 0 ? String(planRow.recommended_kg) : '',
              start_date: todayISO(),
            }}
            fields={[
              { name: 'product_id', label: 'Product', type: 'select', required: true, options: products, placeholder: 'Select product', full: true },
              { name: 'quantity_kg', label: 'Quantity (kg)', type: 'number', required: true, min: 0.01, placeholder: 'Enter quantity in kg' },
              { name: 'line_id', label: 'Production line', type: 'select', required: true, options: lines, placeholder: 'Select line' },
              { name: 'start_date', label: 'Start date', type: 'date', required: true },
              {
                name: 'due_date',
                label: 'Due date',
                type: 'date',
                required: true,
                validate: (v, values) => (values.start_date && v < values.start_date ? 'Due date cannot be before the start date' : undefined),
              },
            ]}
            onSubmit={onSchedule}
          />
        )
      }}
    </OptionsGate>
  )
}
