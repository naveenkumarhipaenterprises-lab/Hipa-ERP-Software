import { ShoppingCart } from 'lucide-react'
import { supplyChainApi } from '../../../api/supplyChainApi'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { useApi } from '../../../hooks/useApi'
import { todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])
const noPurchase = (v) => !v.purchase_id

/**
 * New shipment (POST /supply-chain/shipments/). Linked to an open purchase, the supplier, item, unit and
 * remaining quantity come from it; otherwise the supplier and raw material are chosen here.
 * `options` is the useApi result: loading and errors are shown as such, never as "no purchases".
 */
export function NewShipmentModal({ open, options, onClose, onSubmit }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="New Shipment" onClose={onClose} loadingLabel="Loading purchases…">
      {(o) => <NewShipmentForm o={o} onClose={onClose} onSubmit={onSubmit} />}
    </OptionsGate>
  )
}

function NewShipmentForm({ o, onClose, onSubmit }) {
  const purchases = list(o.purchases)
  const fields = [
    {
      name: 'purchase_id', label: 'Purchase', type: 'select', full: true,
      placeholder: purchases.length ? 'No purchase: choose supplier and material' : 'No open purchase: choose supplier and material',
      // Only purchases still waiting for goods (Pending / Partially Received) can be linked
      hint: purchases.length ? undefined
        : 'Every purchase is already fully received or cancelled. A shipment can be linked to a Pending or Partially Received purchase.',
      options: purchases.map((p) => ({ value: String(p.id), label: `${p.purchase_number} · ${p.supplier} · ${p.item} (${p.quantity} ${p.unit} to receive)` })),
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
      open
      onClose={onClose}
      title="New Shipment"
      subtitle="Track an inbound delivery. Stock is added later by the goods receipt in Purchase."
      fields={fields}
      submitLabel="Create Shipment"
      onSubmit={onSubmit}
    />
  )
}

/**
 * Links a shipment saved without a purchase to an open purchase (Pending / Partially Received) from the same
 * supplier for the same item and unit. Only the link changes; stock is still added by the goods receipt.
 */
export function LinkPurchaseModal({ shipment, onClose, onSubmit }) {
  if (!shipment) return null
  return <LinkPurchase shipment={shipment} onClose={onClose} onSubmit={onSubmit} />
}

function LinkPurchase({ shipment, onClose, onSubmit }) {
  const purchases = useApi(() => supplyChainApi.getLinkablePurchases(shipment.id), [shipment.id])
  const title = `Link ${shipment.shipment_number} to a purchase`
  return (
    <OptionsGate options={purchases} title={title} onClose={onClose} loadingLabel="Loading purchases…">
      {(rows) =>
        list(rows).length === 0 ? (
          <Modal open onClose={onClose} title={title} size="sm">
            <EmptyState
              compact
              icon={ShoppingCart}
              title="No open purchase to link"
              message={`There is no Pending or Partially Received purchase from ${shipment.supplier} for ${shipment.item} (${shipment.unit}). Record it in Purchase first, then link it here.`}
            />
          </Modal>
        ) : (
          <FormModal
            open
            onClose={onClose}
            title={title}
            subtitle={`${shipment.supplier} · ${shipment.item} · ${shipment.quantity} ${shipment.unit}. Only the link is saved; stock is added by the goods receipt in Purchase.`}
            fields={[{
              name: 'purchase_id', label: 'Purchase', type: 'select', required: true, full: true, placeholder: 'Select purchase',
              options: list(rows).map((p) => ({ value: String(p.id), label: `${p.purchase_number} · ${p.supplier} · ${p.item} (${p.quantity} ${p.unit} to receive)` })),
            }]}
            submitLabel="Link Purchase"
            onSubmit={(values) => onSubmit(values.purchase_id)}
          />
        )
      }
    </OptionsGate>
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
