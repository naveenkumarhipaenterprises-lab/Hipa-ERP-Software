import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { formatKg } from '../../../utils/formatters'

/**
 * Stock In / Stock Out form (POST /inventory/movements/). Items come from GET /inventory/options/.
 * Stock Out is checked against the item's current stock before sending; the backend checks again.
 */
export default function StockMovementModal({ type, onClose, options, onSubmit }) {
  if (!type) return null
  return (
    <OptionsGate options={options} title={type === 'out' ? 'Stock Out' : 'Stock In'} onClose={onClose} loadingLabel="Loading products…">
      {(data) => <MovementForm type={type} data={data} onClose={onClose} onSubmit={onSubmit} />}
    </OptionsGate>
  )
}

function MovementForm({ type, data, onClose, onSubmit }) {
  const title = type === 'out' ? 'Stock Out' : 'Stock In'
  const items = Array.isArray(data.items) ? data.items : []
  if (items.length === 0) {
    return (
      <Modal open onClose={onClose} title={title} size="sm">
        <EmptyState compact title="No products in inventory" message="Add a product first, then record stock against it." />
      </Modal>
    )
  }

  const submit = async (values) => {
    const item = items.find((i) => String(i.id) === values.item_id)
    if (type === 'out' && item && Number(item.stock_kg) < values.quantity_kg) {
      const err = new Error(`Only ${formatKg(item.stock_kg)} of ${item.name} is in stock.`)
      err.fields = { quantity_kg: [err.message] }
      throw err
    }
    await onSubmit({ ...values, type, note: values.note?.trim() || undefined })
  }

  return (
    <FormModal
      open
      onClose={onClose}
      title={title}
      subtitle={type === 'out' ? 'Record stock dispatched or used' : 'Record stock received (e.g. from production)'}
      submitLabel={`Record ${title}`}
      fields={[
        {
          name: 'item_id',
          label: 'Product',
          type: 'select',
          required: true,
          full: true,
          placeholder: 'Select product',
          options: items.map((i) => ({
            value: String(i.id),
            label: i.stock_kg != null ? `${i.name} (${formatKg(i.stock_kg)} in stock)` : i.name,
          })),
        },
        { name: 'quantity_kg', label: 'Quantity (kg)', type: 'number', required: true, min: 0.01, placeholder: 'Enter quantity in kg' },
        { name: 'note', label: 'Reference / note', type: 'textarea', placeholder: 'Batch number, PO number, reason…' },
      ]}
      onSubmit={submit}
    />
  )
}
