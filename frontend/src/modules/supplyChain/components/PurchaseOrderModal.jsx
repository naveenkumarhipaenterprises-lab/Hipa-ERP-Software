import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'

const toOptions = (items) => (Array.isArray(items) ? items : []).map((x) => ({ value: String(x.id), label: x.name }))

/** Raises a purchase order (POST /supply-chain/purchase-orders/). Suppliers and materials come from the API. */
export default function PurchaseOrderModal({ open, options, onClose, onCreate }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="New Purchase Order" onClose={onClose} loadingLabel="Loading suppliers and materials…">
      {(data) => {
        const suppliers = toOptions(data.suppliers)
        const materials = toOptions(data.materials)
        if (suppliers.length === 0 || materials.length === 0) {
          return (
            <Modal open onClose={onClose} title="New Purchase Order" size="sm">
              <EmptyState
                compact
                title={suppliers.length === 0 ? 'No suppliers yet' : 'No raw materials set up'}
                message={suppliers.length === 0 ? 'Add a supplier under Manage Suppliers first.' : 'Raw materials must be set up before ordering. Contact your administrator.'}
              />
            </Modal>
          )
        }
        return (
          <FormModal
            open
            onClose={onClose}
            title="New Purchase Order"
            subtitle="Order raw materials from a supplier"
            submitLabel="Raise PO"
            fields={[
              { name: 'material_id', label: 'Material', type: 'select', required: true, options: materials, placeholder: 'Select material' },
              { name: 'supplier_id', label: 'Supplier', type: 'select', required: true, options: suppliers, placeholder: 'Select supplier' },
              { name: 'quantity_kg', label: 'Quantity (kg)', type: 'number', required: true, min: 0.01, placeholder: 'Enter quantity in kg' },
              { name: 'rate_per_kg', label: 'Rate per kg (₹)', type: 'number', min: 0, placeholder: 'Agreed rate, if known' },
              {
                name: 'expected_delivery',
                label: 'Expected delivery',
                type: 'date',
                required: true,
                validate: (v) => (v < todayISO() ? 'Delivery date cannot be in the past' : undefined),
              },
              { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'Quality requirements, delivery instructions…' },
            ]}
            onSubmit={(values) =>
              onCreate({
                ...values,
                rate_per_kg: values.rate_per_kg === '' ? undefined : values.rate_per_kg,
                notes: values.notes?.trim() || undefined,
              })
            }
          />
        )
      }}
    </OptionsGate>
  )
}
