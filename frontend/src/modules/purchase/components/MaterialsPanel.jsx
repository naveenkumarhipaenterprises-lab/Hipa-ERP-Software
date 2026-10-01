import { Eye, Leaf, MinusCircle, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { purchaseApi } from '../../../api/purchaseApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { usePagedList } from '../../../hooks/usePagedList'
import { useToast } from '../../../hooks/useToast'
import { todayISO } from '../../../utils/formatters'
import { choiceOptions, dash, date, idOptions, list, money, optionalNumber, optionalText, qty, withAll } from '../shared'
import ListToolbar from './ListToolbar'

const STOCK_FILTERS = [
  { value: '', label: 'All stock levels' },
  { value: 'low', label: 'At or below reorder level' },
  { value: 'out', label: 'Out of stock' },
  { value: 'in_stock', label: 'In stock' },
]

/**
 * Raw materials: master data (category, unit, minimum / reorder level, usual supplier, standard price)
 * and stock, which changes only through goods receipts, returns and recorded usage.
 */
export default function MaterialsPanel({ options, canManage, canRecordUsage, refreshKey, onChanged }) {
  const toast = useToast()
  const o = options.data ?? {}
  const [editing, setEditing] = useState(null)
  const [using, setUsing] = useState(null)
  const [viewing, setViewing] = useState(null)
  const [removing, setRemoving] = useState(null)
  const l = usePagedList(purchaseApi.listMaterials, { category: '', status: '', stock_status: '' }, refreshKey)

  const save = async (v) => {
    const body = {
      ...v,
      supplier_id: v.supplier_id || null,
      purchase_price: optionalNumber(v.purchase_price) ?? null,
      opening_stock: editing.id ? undefined : optionalNumber(v.opening_stock),
    }
    const m = editing.id ? await purchaseApi.updateMaterial(editing.id, body) : await purchaseApi.createMaterial(body)
    toast.success(editing.id ? `${m.name} updated` : `${m.name} added (${m.material_code})`)
    onChanged()
  }

  const recordUsage = async (v) => {
    await purchaseApi.recordMaterialMovement({ material_id: using.id, type: v.type, quantity: v.quantity, date: v.date, note: optionalText(v.note),
                                               source: v.type === 'out' ? v.source : 'adjustment' })
    toast.success(`Stock of ${using.name} updated`)
    onChanged()
  }

  const remove = async () => {
    await purchaseApi.deleteMaterial(removing.id)
    toast.success(`${removing.name} deleted`)
    onChanged()
  }

  const fields = [
    { name: 'name', label: 'Material name', required: true, full: true },
    { name: 'category', label: 'Category', type: 'select', required: true, options: choiceOptions(o.categories) },
    { name: 'unit', label: 'Unit', type: 'select', required: true, options: choiceOptions(o.units) },
    { name: 'minimum_stock', label: 'Minimum stock', type: 'number', min: 0, placeholder: '0' },
    { name: 'reorder_level', label: 'Reorder level', type: 'number', min: 0, placeholder: '0',
      validate: (v, vals) => (Number(v || 0) < Number(vals.minimum_stock || 0) ? "Can't be below the minimum stock" : undefined) },
    { name: 'supplier_id', label: 'Usual supplier', type: 'select', options: idOptions(o.suppliers), placeholder: 'None' },
    { name: 'purchase_price', label: 'Standard purchase price (₹ per unit)', type: 'number', min: 0 },
    ...(editing?.id
      ? [{ name: 'status', label: 'Status', type: 'select', required: true, options: choiceOptions(o.material_statuses) }]
      : [{ name: 'opening_stock', label: 'Opening stock', type: 'number', min: 0, placeholder: 'Stock on hand today' }]),
  ]

  const columns = [
    { key: 'material_code', header: 'Material ID', render: (r) => <span className="nowrap">{r.material_code}</span> },
    { key: 'name', header: 'Material', render: (r) => <strong>{r.name}</strong> },
    { key: 'category_label', header: 'Category' },
    { key: 'current_stock', header: 'Current Stock', align: 'right', render: (r) => qty(r.current_stock, r.unit) },
    { key: 'minimum_stock', header: 'Minimum', align: 'right', render: (r) => qty(r.minimum_stock, r.unit) },
    { key: 'reorder_level', header: 'Reorder Level', align: 'right', render: (r) => qty(r.reorder_level, r.unit) },
    { key: 'supplier', header: 'Supplier', render: (r) => dash(r.supplier) },
    { key: 'purchase_price', header: 'Purchase Price', align: 'right', render: (r) => money(r.purchase_price) },
    { key: 'stock_status', header: 'Stock', render: (r) => <Badge>{r.stock_status}</Badge> },
    { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
    {
      key: 'actions', sticky: true, header: <span className="sr-only">Actions</span>, align: 'right',
      render: (r) => (
        <span className="row-actions">
          <Button size="sm" variant="ghost" icon={Eye} onClick={() => setViewing(r)} aria-label={`View ${r.name}`} />
          {canRecordUsage && r.status === 'Active' && (
            <Button size="sm" variant="ghost" icon={MinusCircle} onClick={() => setUsing(r)} aria-label={`Record usage of ${r.name}`} />
          )}
          {canManage && <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setEditing(r)} aria-label={`Edit ${r.name}`} />}
          {canManage && <Button size="sm" variant="ghost" icon={Trash2} onClick={() => setRemoving(r)} aria-label={`Delete ${r.name}`} />}
        </span>
      ),
    },
  ]

  return (
    <Card title="Raw Materials" subtitle="Stock changes through goods receipts, returns and recorded usage" bodyClassName="card__body--flush"
          action={canManage && <Button size="sm" icon={Plus} onClick={() => setEditing({})}>Add Material</Button>}>
      <ListToolbar
        search={l.search} onSearch={l.setSearch} searchLabel="Search material, ID or supplier" onFilter={l.setFilter}
        filters={[
          { name: 'category', label: 'Filter by category', value: l.filters.category, options: withAll('All categories', choiceOptions(o.categories)) },
          { name: 'stock_status', label: 'Filter by stock', value: l.filters.stock_status, options: STOCK_FILTERS },
          { name: 'status', label: 'Filter by status', value: l.filters.status, options: withAll('All statuses', choiceOptions(o.material_statuses)) },
        ]}
      />
      {l.result.error && !l.result.loading ? (
        <div className="card__pad">
          <ErrorMessage message={l.result.error.message} onRetry={l.result.reload} />
        </div>
      ) : (
        <Table loading={l.result.loading} caption="Raw materials" data={l.rows} columns={columns} emptyIcon={Leaf}
               emptyTitle={l.filtered ? 'No materials match' : 'No raw materials yet'}
               emptyMessage={l.filtered ? 'Try another search or filter.' : 'Add the raw spices and packing materials you buy.'}
               pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }} />
      )}

      <FormModal
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        title={editing?.id ? `Edit ${editing.name}` : 'Add Raw Material'}
        subtitle={editing?.id ? editing.material_code : 'The material ID is assigned automatically'}
        submitLabel={editing?.id ? 'Save Changes' : 'Add Material'}
        initialValues={editing?.id ? { ...editing, supplier_id: editing.supplier_id ? String(editing.supplier_id) : '', purchase_price: editing.purchase_price ?? '' } : { unit: 'kg' }}
        fields={fields}
        onSubmit={save}
      />
      <FormModal
        open={Boolean(using)}
        onClose={() => setUsing(null)}
        title={`Stock movement: ${using?.name ?? ''}`}
        subtitle={using ? `In stock: ${qty(using.current_stock, using.unit)}. Usage feeds the AI purchase recommendations.` : ''}
        submitLabel="Save"
        initialValues={{ type: 'out', source: 'usage', date: todayISO() }}
        fields={[
          { name: 'type', label: 'Movement', type: 'select', required: true, options: [{ value: 'out', label: 'Stock out' }, { value: 'in', label: 'Stock in (correction)' }] },
          { name: 'source', label: 'Reason', type: 'select', required: true, visible: (v) => v.type === 'out',
            options: [{ value: 'usage', label: 'Used in processing / packing' }, { value: 'adjustment', label: 'Correction (loss, count difference)' }] },
          { name: 'quantity', label: `Quantity${using ? ` (${using.unit})` : ''}`, type: 'number', required: true, min: 0.001,
            validate: (v, vals) => (vals.type === 'out' && using && Number(v) > Number(using.current_stock) ? `Only ${qty(using.current_stock, using.unit)} in stock` : undefined) },
          { name: 'date', label: 'Date', type: 'date', required: true, validate: (v) => (v > todayISO() ? "Can't be in the future" : undefined) },
          { name: 'note', label: 'Note', type: 'textarea' },
        ]}
        onSubmit={recordUsage}
      />
      <MaterialDetail material={viewing} onClose={() => setViewing(null)} />
      <ConfirmDialog open={Boolean(removing)} onClose={() => setRemoving(null)} onConfirm={remove} danger title="Delete raw material?"
                     message={`${removing?.name ?? ''} will be deleted. Materials with stock movements or purchases can't be deleted — set them to Inactive instead.`}
                     confirmLabel="Delete" />
    </Card>
  )
}

function MaterialDetail({ material, onClose }) {
  const detail = useApi(() => (material ? purchaseApi.getMaterial(material.id) : Promise.resolve(null)), [material?.id])
  if (!material) return null
  const m = detail.data
  return (
    <Modal open onClose={onClose} title={material.name} subtitle={material.material_code} size="lg">
      {detail.error && !detail.loading ? (
        <ErrorMessage message={detail.error.message} onRetry={detail.reload} />
      ) : !m ? (
        <Loader label="Loading material…" />
      ) : (
        <div className="stack">
          <dl className="detail-grid">
            {[['Category', m.category_label], ['Unit', m.unit], ['Current stock', qty(m.current_stock, m.unit)], ['Minimum stock', qty(m.minimum_stock, m.unit)],
              ['Reorder level', qty(m.reorder_level, m.unit)], ['Usual supplier', dash(m.supplier)], ['Standard price', money(m.purchase_price)],
              ['Stock status', m.stock_status], ['Status', m.status]].map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
          <h3 className="card__title">Price history</h3>
          <Table compact caption="Price history" data={list(m.price_history)} emptyTitle="No purchases yet" emptyMessage="Prices paid will be listed here."
                 columns={[{ key: 'purchase_number', header: 'Purchase' }, { key: 'date', header: 'Date', render: (r) => date(r.date) },
                           { key: 'supplier', header: 'Supplier' }, { key: 'unit_price', header: 'Unit price', align: 'right', render: (r) => money(r.unit_price) }]} />
          <h3 className="card__title">Recent stock movements</h3>
          <Table compact caption="Stock movements" data={list(m.movements)} emptyTitle="No stock movements" emptyMessage="Receipts, returns and usage will be listed here."
                 columns={[{ key: 'date', header: 'Date', render: (r) => date(r.date) }, { key: 'source', header: 'Type' },
                           { key: 'quantity', header: 'Quantity', align: 'right', render: (r) => `${r.type === 'out' ? '−' : '+'}${qty(r.quantity, r.unit)}` },
                           { key: 'reference', header: 'Reference', render: (r) => dash(r.reference) }, { key: 'note', header: 'Note', render: (r) => dash(r.note) }]} />
        </div>
      )}
    </Modal>
  )
}
