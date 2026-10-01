import { FlaskConical } from 'lucide-react'
import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])

/**
 * Records lab results (POST /quality/tests/) for one lot of:
 *  - goods received from a supplier that are waiting for inspection (the GRN's quality status follows the result),
 *  - a finished product, or
 *  - a raw material.
 */
export default function TestEntryModal({ open, options, onClose, onSave }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="New Test Entry" onClose={onClose} loadingLabel="Loading items to test…">
      {(data) => {
        const receipts = list(data.pending_receipts).map((g) => ({
          value: String(g.id),
          label: `${g.grn_number} • ${g.item} • ${g.supplier} (${g.quality_status})`,
        }))
        const products = list(data.products).map((p) => ({ value: String(p.id), label: p.name }))
        const materials = list(data.materials).map((m) => ({ value: String(m.id), label: m.name }))
        const sources = [
          receipts.length && { value: 'receipt', label: 'Goods received (awaiting inspection)' },
          products.length && { value: 'product', label: 'Finished product' },
          materials.length && { value: 'material', label: 'Raw material' },
        ].filter(Boolean)

        if (sources.length === 0 || list(data.results).length === 0) {
          return (
            <Modal open onClose={onClose} title="New Test Entry" size="sm">
              <EmptyState
                compact
                icon={FlaskConical}
                title={sources.length === 0 ? 'Nothing to test yet' : 'Test results are not set up'}
                message={sources.length === 0
                  ? 'Goods receipts waiting for inspection, products and raw materials will be offered here once they exist.'
                  : 'Contact your administrator.'}
              />
            </Modal>
          )
        }
        return (
          <FormModal
            open
            onClose={onClose}
            title="New Test Entry"
            subtitle="Record lab results for one lot"
            submitLabel="Save Result"
            initialValues={{ source: sources[0].value, test_date: todayISO() }}
            fields={[
              { name: 'source', label: 'Testing', type: 'select', required: true, options: sources, full: true },
              { name: 'goods_receipt_id', label: 'Goods receipt', type: 'select', required: true, options: receipts, placeholder: 'Select GRN', full: true,
                visible: (v) => v.source === 'receipt' },
              { name: 'product_id', label: 'Product', type: 'select', required: true, options: products, placeholder: 'Select product',
                visible: (v) => v.source === 'product' },
              { name: 'material_id', label: 'Raw material', type: 'select', required: true, options: materials, placeholder: 'Select material',
                visible: (v) => v.source === 'material' },
              { name: 'batch_number', label: 'Lot / batch number', placeholder: 'As printed on the lot' },
              { name: 'test_date', label: 'Test date', type: 'date', required: true,
                validate: (v) => (v > todayISO() ? 'Test date cannot be in the future' : undefined) },
              { name: 'result', label: 'Result', type: 'select', required: true, options: data.results, placeholder: 'Select result' },
              { name: 'parameters', label: 'Parameters tested', required: true, full: true, placeholder: 'List the parameters checked' },
              { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'Readings, observations or reasons for failure' },
            ]}
            // Only the visible item field is sent (goods_receipt_id, product_id or material_id); `source` is ignored by the API
            onSubmit={(values) =>
              onSave({ ...values, parameters: values.parameters.trim(), batch_number: values.batch_number?.trim() || undefined,
                       notes: values.notes?.trim() || undefined })
            }
          />
        )
      }}
    </OptionsGate>
  )
}
