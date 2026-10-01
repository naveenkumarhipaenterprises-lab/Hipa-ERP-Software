import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'
import { choiceOptions, idOptions, list, money, optionalNumber, optionalText, qty } from '../shared'

const notFuture = (v) => (v > todayISO() ? "Can't be in the future" : undefined)
const purchaseLabel = (p) => `${p.purchase_number} · ${p.supplier} · ${p.item}`

function Unavailable({ title, message, onClose }) {
  return (
    <Modal open onClose={onClose} title={title} size="sm">
      <EmptyState compact title={message.title} message={message.text} />
    </Modal>
  )
}

/** Goods receipt (GRN) against a purchase. Only the accepted quantity is added to stock. */
export function GoodsReceiptModal({ open, purchase, options, onClose, onSave }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="Goods Receipt" onClose={onClose}>
      {(data) => {
        const open_ = list(data.purchases).filter((p) => Number(p.pending_quantity) > 0)
        if (!purchase && open_.length === 0)
          return <Unavailable title="Goods Receipt" onClose={onClose} message={{ title: 'Nothing to receive', text: 'Every purchase is fully received. Record a purchase first.' }} />
        const find = (id) => open_.find((p) => String(p.id) === String(id)) ?? (purchase && String(purchase.id) === String(id) ? purchase : null)
        return (
          <FormModal
            open
            onClose={onClose}
            title="Record Goods Receipt"
            subtitle="GRN number is assigned automatically. Accepted quantity = received − damaged unless you enter less."
            submitLabel="Save Receipt"
            initialValues={{ purchase_id: purchase ? String(purchase.id) : '', received_date: todayISO(), quality_status: 'Pending Inspection' }}
            fields={[
              { name: 'purchase_id', label: 'Purchase', type: 'select', required: true, full: true,
                options: (purchase && !find(purchase.id) ? [purchase] : []).concat(open_).map((p) => ({ value: String(p.id), label: `${purchaseLabel(p)} · ${qty(p.pending_quantity, p.unit)} to receive` })) },
              { name: 'received_date', label: 'Received date', type: 'date', required: true, validate: notFuture },
              { name: 'received_quantity', label: 'Received quantity', type: 'number', required: true, min: 0.001,
                validate: (v, vals) => {
                  const p = find(vals.purchase_id)
                  return p && Number(v) > Number(p.pending_quantity) ? `Only ${qty(p.pending_quantity, p.unit)} is still to be received` : undefined
                } },
              { name: 'damaged_quantity', label: 'Damaged quantity', type: 'number', min: 0, placeholder: '0',
                validate: (v, vals) => (Number(v) > Number(vals.received_quantity) ? "Can't exceed the received quantity" : undefined) },
              { name: 'accepted_quantity', label: 'Accepted quantity', type: 'number', min: 0, placeholder: 'Received − damaged',
                validate: (v, vals) => (v !== '' && Number(v) > Number(vals.received_quantity || 0) - Number(vals.damaged_quantity || 0) ? "Can't exceed received − damaged" : undefined) },
              { name: 'quality_status', label: 'Quality status', type: 'select', required: true, options: choiceOptions(data.quality_statuses) },
              { name: 'remarks', label: 'Remarks', type: 'textarea' },
            ]}
            summary={(v) => {
              const p = find(v.purchase_id)
              return p ? <p className="muted">Unit: {p.unit}. Already received: {qty(p.received_quantity, p.unit)}.</p> : null
            }}
            onSubmit={(v) => onSave({ ...v, damaged_quantity: optionalNumber(v.damaged_quantity), accepted_quantity: optionalNumber(v.accepted_quantity), remarks: optionalText(v.remarks) })}
          />
        )
      }}
    </OptionsGate>
  )
}

/** Goods returned to a supplier. The amount defaults to the purchase's effective price when left blank. */
export function PurchaseReturnModal({ open, purchase, options, onClose, onSave }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="Purchase Return" onClose={onClose}>
      {(data) => {
        const received = list(data.purchases).filter((p) => Number(p.received_quantity) > 0)
        if (!purchase && received.length === 0)
          return <Unavailable title="Purchase Return" onClose={onClose} message={{ title: 'Nothing to return', text: 'Returns are recorded against purchases with goods received.' }} />
        const choices = (purchase && !received.some((p) => p.id === purchase.id) ? [purchase] : []).concat(received)
        return (
          <FormModal
            open
            onClose={onClose}
            title="Record Purchase Return"
            subtitle="Stock goes out when the return is saved, and back in if it is cancelled"
            submitLabel="Save Return"
            initialValues={{ purchase_id: purchase ? String(purchase.id) : '', return_date: todayISO() }}
            fields={[
              { name: 'purchase_id', label: 'Purchase', type: 'select', required: true, full: true,
                options: choices.map((p) => ({ value: String(p.id), label: `${purchaseLabel(p)} · ${qty(p.received_quantity, p.unit)} received` })) },
              { name: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0.001 },
              { name: 'return_date', label: 'Return date', type: 'date', required: true, validate: notFuture },
              { name: 'reason', label: 'Reason', type: 'select', required: true, options: choiceOptions(data.return_reasons) },
              { name: 'amount', label: 'Amount (₹)', type: 'number', min: 0, placeholder: 'Blank = at the purchase price' },
              { name: 'remarks', label: 'Remarks', type: 'textarea' },
            ]}
            onSubmit={(v) => onSave({ ...v, amount: optionalNumber(v.amount), remarks: optionalText(v.remarks) })}
          />
        )
      }}
    </OptionsGate>
  )
}

/** A payment made to a supplier, or a scheduled one (Pending; shown as Overdue once its date passes). */
export function SupplierPaymentModal({ open, purchase, options, onClose, onSave }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="Supplier Payment" onClose={onClose}>
      {(data) => {
        const suppliers = idOptions(data.suppliers)
        const payable = list(data.purchases).filter((p) => Number(p.balance) > 0)
        if (suppliers.length === 0 && !purchase)
          return <Unavailable title="Supplier Payment" onClose={onClose} message={{ title: 'No suppliers', text: 'Add a supplier first.' }} />
        const findP = (id) => payable.find((p) => String(p.id) === String(id)) ?? (purchase && String(purchase.id) === String(id) ? purchase : null)
        return (
          <FormModal
            open
            onClose={onClose}
            title="Record Supplier Payment"
            subtitle="Payment ID is assigned automatically"
            submitLabel="Save Payment"
            initialValues={{
              purchase_id: purchase ? String(purchase.id) : '',
              supplier_id: purchase ? String(purchase.supplier_id) : '',
              amount: purchase?.balance > 0 ? purchase.balance : '',
              payment_date: todayISO(),
              status: 'paid',
            }}
            fields={[
              { name: 'purchase_id', label: 'Purchase (optional)', type: 'select', full: true, placeholder: 'Not for one purchase',
                options: (purchase && !payable.some((p) => p.id === purchase.id) ? [purchase] : []).concat(payable)
                  .map((p) => ({ value: String(p.id), label: `${purchaseLabel(p)} · ${money(p.balance)} due` })) },
              { name: 'supplier_id', label: 'Supplier', type: 'select', required: true, options: suppliers, visible: (v) => !v.purchase_id },
              { name: 'amount', label: 'Amount (₹)', type: 'number', required: true, min: 0.01,
                validate: (v, vals) => {
                  const p = findP(vals.purchase_id)
                  return p && Number(v) > Number(p.balance) ? `Only ${money(p.balance)} is outstanding` : undefined
                } },
              { name: 'status', label: 'Payment', type: 'select', required: true,
                options: [{ value: 'paid', label: 'Paid now' }, { value: 'pending', label: 'Schedule (pending)' }] },
              { name: 'payment_date', label: 'Payment date', type: 'date', required: true,
                validate: (v, vals) => (vals.status === 'paid' ? notFuture(v) : undefined) },
              { name: 'payment_method', label: 'Payment method', type: 'select', required: true, options: choiceOptions(data.payment_methods) },
              { name: 'transaction_reference', label: 'Transaction reference', placeholder: 'UTR / cheque no.' },
              { name: 'notes', label: 'Notes', type: 'textarea' },
            ]}
            onSubmit={(v) => onSave({ ...v, purchase_id: v.purchase_id || undefined, supplier_id: v.purchase_id ? undefined : v.supplier_id,
                                      transaction_reference: optionalText(v.transaction_reference), notes: optionalText(v.notes) })}
          />
        )
      }}
    </OptionsGate>
  )
}
