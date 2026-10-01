import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import TotalsSummary from '../../../components/common/TotalsSummary'
import { todayISO } from '../../../utils/formatters'
import { lineTotals } from '../../../utils/money'
import { idOptions, list, optionalNumber, optionalText } from '../shared'

const ITEM_TYPES = [
  { value: 'material', label: 'Raw material' },
  { value: 'product', label: 'Finished product' },
]
const pctRule = (v) => (Number(v) > 100 ? 'At most 100%' : undefined)

/**
 * Record a purchase, or edit one. A purchase that already has goods receipts, payments or returns
 * can only change its dates and notes (`purchase.can_edit_all` is false).
 * `prefill` (e.g. from an AI recommendation): { item_type, material_id | product_id, quantity, supplier_id }
 */
export default function PurchaseFormModal({ open, purchase, prefill, options, onClose, onSave }) {
  if (!open) return null
  const limited = purchase && !purchase.can_edit_all

  if (limited) {
    return (
      <FormModal
        open
        onClose={onClose}
        title={`Edit ${purchase.purchase_number}`}
        subtitle="Goods, payments or returns are recorded, so only dates and notes can change"
        submitLabel="Save Changes"
        initialValues={{
          expected_receipt_date: purchase.expected_receipt_date ?? '',
          payment_due_date: purchase.payment_due_date ?? '',
          notes: purchase.notes ?? '',
        }}
        fields={[
          { name: 'expected_receipt_date', label: 'Expected receipt date', type: 'date' },
          { name: 'payment_due_date', label: 'Payment due date', type: 'date' },
          { name: 'notes', label: 'Notes', type: 'textarea' },
        ]}
        onSubmit={(v) => onSave({ expected_receipt_date: v.expected_receipt_date || null, payment_due_date: v.payment_due_date || null, notes: v.notes })}
      />
    )
  }

  return (
    <OptionsGate options={options} title="Purchase" onClose={onClose} loadingLabel="Loading suppliers and materials…">
      {(data) => {
        const suppliers = idOptions(data.suppliers)
        const materials = list(data.materials)
        const products = list(data.products)
        if (suppliers.length === 0 || (materials.length === 0 && products.length === 0)) {
          return (
            <Modal open onClose={onClose} title="Record Purchase" size="sm">
              <EmptyState
                compact
                title={suppliers.length === 0 ? 'No active suppliers' : 'No raw materials or products'}
                message={suppliers.length === 0 ? 'Add a supplier first (Purchase → Suppliers).' : 'Add a raw material (Purchase → Raw Materials) or a product (Inventory) first.'}
              />
            </Modal>
          )
        }
        const priceOf = (values) => {
          if (values.unit_price !== '' && values.unit_price !== undefined) return values.unit_price
          const m = values.item_type === 'material' && materials.find((x) => String(x.id) === String(values.material_id))
          return m?.purchase_price ?? 0
        }
        const unitOf = (values) =>
          values.item_type === 'product' ? 'kg' : materials.find((x) => String(x.id) === String(values.material_id))?.unit ?? ''
        const src = purchase ?? prefill ?? {}

        return (
          <FormModal
            open
            onClose={onClose}
            title={purchase ? `Edit ${purchase.purchase_number}` : 'Record Purchase'}
            subtitle={purchase ? 'Totals are recalculated when you save' : 'Purchase ID is assigned automatically. No purchase order or purchase invoice is created.'}
            submitLabel={purchase ? 'Save Changes' : 'Save Purchase'}
            initialValues={{
              supplier_id: src.supplier_id != null ? String(src.supplier_id) : '',
              item_type: src.item_type ?? (materials.length ? 'material' : 'product'),
              material_id: src.material_id != null ? String(src.material_id) : '',
              product_id: src.product_id != null ? String(src.product_id) : '',
              quantity: src.quantity ?? '',
              unit_price: src.unit_price ?? '',
              discount_pct: src.discount_pct ?? '',
              gst_pct: src.gst_pct ?? '',
              purchase_date: src.purchase_date ?? todayISO(),
              expected_receipt_date: src.expected_receipt_date ?? '',
              payment_due_date: src.payment_due_date ?? '',
              notes: src.notes ?? '',
            }}
            fields={[
              { name: 'supplier_id', label: 'Supplier', type: 'select', required: true, options: suppliers, full: true },
              { name: 'item_type', label: 'Buying', type: 'select', required: true, options: ITEM_TYPES.filter((t) => (t.value === 'material' ? materials.length : products.length)) },
              {
                name: 'material_id', label: 'Raw material', type: 'select', required: true,
                options: materials.map((m) => ({ value: String(m.id), label: `${m.name} (${m.unit})` })),
                visible: (v) => v.item_type === 'material',
              },
              { name: 'product_id', label: 'Product', type: 'select', required: true, options: idOptions(products), visible: (v) => v.item_type === 'product' },
              { name: 'quantity', label: 'Quantity', type: 'number', required: true, min: 0.001 },
              { name: 'unit_price', label: 'Unit price (₹)', type: 'number', min: 0, placeholder: "Blank = material's standard price" },
              { name: 'discount_pct', label: 'Discount %', type: 'number', min: 0, placeholder: '0', validate: pctRule },
              { name: 'gst_pct', label: 'GST / Tax %', type: 'number', min: 0, placeholder: 'Default from Settings', validate: pctRule },
              { name: 'purchase_date', label: 'Purchase date', type: 'date', required: true, validate: (v) => (v > todayISO() ? "Can't be in the future" : undefined) },
              {
                name: 'expected_receipt_date', label: 'Expected receipt date', type: 'date',
                validate: (v, vals) => (v && vals.purchase_date && v < vals.purchase_date ? "Can't be before the purchase date" : undefined),
              },
              {
                name: 'payment_due_date', label: 'Payment due date', type: 'date', placeholder: "Blank = from supplier's credit days",
                validate: (v, vals) => (v && vals.purchase_date && v < vals.purchase_date ? "Can't be before the purchase date" : undefined),
              },
              { name: 'notes', label: 'Notes', type: 'textarea' },
            ]}
            summary={(v) => (
              <TotalsSummary
                totals={lineTotals(v.quantity, priceOf(v), v.discount_pct, v.gst_pct)}
                extra={unitOf(v) ? [{ label: 'Unit', value: unitOf(v) }] : []}
              />
            )}
            onSubmit={(v) =>
              onSave({
                supplier_id: v.supplier_id,
                item_type: v.item_type,
                material_id: v.item_type === 'material' ? v.material_id : undefined,
                product_id: v.item_type === 'product' ? v.product_id : undefined,
                quantity: v.quantity,
                unit_price: optionalNumber(v.unit_price),
                discount_pct: optionalNumber(v.discount_pct),
                gst_pct: optionalNumber(v.gst_pct),
                purchase_date: v.purchase_date,
                expected_receipt_date: v.expected_receipt_date || null,
                payment_due_date: v.payment_due_date || null,
                notes: optionalText(v.notes) ?? '',
              })
            }
          />
        )
      }}
    </OptionsGate>
  )
}
