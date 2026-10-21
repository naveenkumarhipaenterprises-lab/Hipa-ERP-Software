import { ClipboardList, Pencil, Plus } from 'lucide-react'
import { useState } from 'react'
import { qualityApi } from '../../../api/qualityApi'
import Button from '../../../components/common/Button'
import DeleteRecordButton from '../../../components/common/DeleteRecordButton'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''

/** "0 – 10", "≥ 2", "≤ 10" or "Not checked" from a standard's optional lowest / highest values. */
function checkRange(s) {
  if (has(s.min_value) && has(s.max_value)) return `${s.min_value} – ${s.max_value}`
  if (has(s.min_value)) return `≥ ${s.min_value}`
  if (has(s.max_value)) return `≤ ${s.max_value}`
  return 'Not checked'
}

/**
 * Acceptance limits applied to batches (GET /quality/standards/). The quality team adds and edits them here
 * (one limit per parameter and product, or for all products); deleting is for Super Admins.
 */
export default function StandardsModal({ open, options, canManage = false, onClose }) {
  if (!open) return null
  return <Standards options={options} canManage={canManage} onClose={onClose} />
}

function Standards({ options, canManage, onClose }) {
  const toast = useToast()
  const [form, setForm] = useState(null) // { standard? }
  const standards = useApi(() => qualityApi.getStandards(), [])
  const rows = list(standards.data)
  const products = list(options?.data?.products).map((p) => ({ value: String(p.id), label: p.name }))
  const s = form?.standard

  const save = async (values) => {
    const body = { ...values, product_id: values.product_id || null }
    const saved = s ? await qualityApi.updateStandard(s.id, body) : await qualityApi.createStandard(body)
    toast.success(s ? `${saved.parameter} updated` : `${saved.parameter} added`)
    standards.reload()
  }

  return (
    <Modal open onClose={onClose} title="Quality Standards" subtitle="Acceptance limits applied to every batch"
           footer={canManage ? <Button icon={Plus} onClick={() => setForm({})}>Add Standard</Button> : undefined}>
      {standards.error && !standards.loading ? (
        <ErrorMessage message={standards.error.message} onRetry={standards.reload} />
      ) : (
        <Table
          compact
          loading={standards.loading}
          caption="Quality standards"
          rowKey={(r, i) => r.id ?? i}
          data={rows}
          emptyIcon={ClipboardList}
          emptyTitle="No standards defined"
          emptyMessage={canManage ? 'Add the acceptance limits your lots must meet, e.g. Moisture ≤ 10%.' : 'The quality team sets the acceptance limits.'}
          columns={[
            { key: 'parameter', header: 'Parameter' },
            { key: 'limit', header: 'Limit' },
            { key: 'check', header: 'Readings checked', render: (r) => <span className={has(r.min_value) || has(r.max_value) ? '' : 'muted'}>{checkRange(r)}</span> },
            { key: 'applies_to', header: 'Applies to', render: (r) => r.applies_to || 'All items' },
            ...(canManage ? [{
              key: 'actions', align: 'right', header: <span className="sr-only">Actions</span>,
              render: (r) => (
                <span className="row-actions">
                  <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setForm({ standard: r })} aria-label={`Edit ${r.parameter}`} />
                  <DeleteRecordButton kind="quality_standard" id={r.id} label={`${r.parameter} standard`} onDeleted={standards.reload} />
                </span>
              ),
            }] : []),
          ]}
        />
      )}
      <FormModal
        open={Boolean(form)}
        onClose={() => setForm(null)}
        title={s ? `Edit ${s.parameter}` : 'Add Standard'}
        subtitle="One limit per parameter and product (or for all products)"
        fields={[
          { name: 'parameter', label: 'Parameter', required: true, placeholder: 'e.g. Moisture' },
          { name: 'limit', label: 'Limit', required: true, placeholder: 'e.g. ≤ 10%' },
          { name: 'min_value', label: 'Lowest acceptable value', type: 'number', placeholder: 'e.g. 0',
            hint: 'Optional. With a lowest and/or highest value, test readings are checked automatically.' },
          { name: 'max_value', label: 'Highest acceptable value', type: 'number', placeholder: 'e.g. 10' },
          { name: 'product_id', label: 'Applies to', type: 'select', full: true, placeholder: 'All items', options: products },
        ]}
        initialValues={s ? { parameter: s.parameter, limit: s.limit, product_id: s.product_id ? String(s.product_id) : '',
                             min_value: s.min_value ?? '', max_value: s.max_value ?? '' } : {}}
        submitLabel="Save"
        onSubmit={save}
      />
    </Modal>
  )
}
