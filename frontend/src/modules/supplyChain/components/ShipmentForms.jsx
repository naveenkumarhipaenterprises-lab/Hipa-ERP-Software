import ConfirmDialog from '../../../components/common/ConfirmDialog'
import FormModal from '../../../components/common/FormModal'
import { todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])
const noPurchase = (v) => !v.purchase_id

/**
 * New shipment (POST /supply-chain/shipments/). Linked to an open purchase, the supplier, item, unit and
 * remaining quantity come from it; otherwise the supplier and raw material are chosen here.
 */
export function NewShipmentModal({ open, options, onClose, onSubmit }) {
  const o = options ?? {}
  const fields = [
    {
      name: 'purchase_id', label: 'Purchase', type: 'select', full: true, placeholder: 'No purchase: choose supplier and material',
      options: list(o.purchases).map((p) => ({ value: String(p.id), label: `${p.purchase_number} · ${p.supplier} · ${p.item} (${p.quantity} ${p.unit} to receive)` })),
    },
    { name: 'supplier_id', label: 'Supplier', type: 'select', required: true, visible: noPurchase,
      options: list(o.suppliers).map((s) => ({ value: String(s.id), label: s.name })) },
    { name: 'material_id', label: 'Raw material', type: 'select', required: true, visible: noPurchase,
      options: list(o.materials).map((m) => ({ value: String(m.id), label: m.name })) },
    { name: 'quantity', label: 'Quantity', type: 'number', min: 0, required: true, visible: noPurchase },
    { name: 'unit', label: 'Unit', type: 'select', required: true, visible: noPurchase, defaultValue: 'kg', options: list(o.units) },
    { name: 'quantity', label: 'Quantity (leave empty for all still to receive)', type: 'number', min: 0, visible: (v) => !noPurchase(v) },
    { name: 'destination', label: 'Destination', required: true, placeholder: 'e.g. Main warehouse' },
    { name: 'dispatched_on', label: 'Dispatched on', type: 'date', required: true, defaultValue: todayISO() },
    { name: 'eta', label: 'Expected arrival', type: 'date', required: true },
  ]
  return (
    <FormModal
      open={open}
      onClose={onClose}
      title="New Shipment"
      subtitle="Track an inbound delivery. Stock is added later by the goods receipt in Purchase."
      fields={fields}
      submitLabel="Create Shipment"
      onSubmit={onSubmit}
    />
  )
}

const DELIVERED_FIELDS = [
  { name: 'delivered_on', label: 'Delivered on', type: 'date', required: true, defaultValue: todayISO() },
  {
    name: 'quality_passed', label: 'Inward quality check', type: 'select', placeholder: 'Not checked',
    options: [{ value: 'true', label: 'Passed' }, { value: 'false', label: 'Failed' }],
  },
]

/** Status change for one shipment: Delayed / back In Transit (confirm) or Delivered (date + quality result). */
export function ShipmentStatusModal({ change, onClose, onSubmit }) {
  if (!change) return null
  const { shipment, status } = change
  if (status === 'delivered') {
    return (
      <FormModal
        open
        onClose={onClose}
        title={`Mark ${shipment.shipment_number} delivered`}
        subtitle="Delivered is final. Book the goods into stock with a goods receipt in Purchase."
        fields={DELIVERED_FIELDS}
        submitLabel="Mark Delivered"
        onSubmit={(values) => onSubmit({ status, ...values })}
      />
    )
  }
  const label = status === 'delayed' ? 'Delayed' : 'In Transit'
  return (
    <ConfirmDialog
      open
      onClose={onClose}
      onConfirm={() => onSubmit({ status })}
      danger={status === 'delayed'}
      title={`Mark ${shipment.shipment_number} ${label.toLowerCase()}?`}
      message={status === 'delayed' ? `Shipment from ${shipment.supplier} will show as delayed and a delay alert is sent.` : `Shipment from ${shipment.supplier} is back on its way.`}
      confirmLabel={`Mark ${label}`}
      cancelLabel="Back"
    />
  )
}
