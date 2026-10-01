import { Eye, Pencil, Plus, Trash2, Users } from 'lucide-react'
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
import { isGstin } from '../../../utils/validation'
import { choiceOptions, dash, date, list, money, optionalNumber, withAll } from '../shared'
import ListToolbar from './ListToolbar'
import { PURCHASE_COLUMNS } from './purchaseColumns'

const SORTS = [
  { value: 'name', label: 'Name A–Z' },
  { value: '-name', label: 'Name Z–A' },
  { value: '-value', label: 'Highest purchases' },
  { value: '-created_at', label: 'Newest first' },
  { value: 'city', label: 'City' },
]

const supplierFields = (statuses, editing) => [
  { name: 'name', label: 'Supplier name', required: true },
  { name: 'company_name', label: 'Company name' },
  { name: 'contact_person', label: 'Contact person' },
  { name: 'phone', label: 'Phone', placeholder: 'e.g. 98765 43210' },
  { name: 'email', label: 'Email', type: 'email' },
  { name: 'gstin', label: 'GSTIN', placeholder: '15 characters', validate: (v) => (v && !isGstin(v) ? 'Enter a valid 15-character GSTIN' : undefined) },
  { name: 'address', label: 'Address', type: 'textarea' },
  { name: 'city', label: 'City', required: true },
  { name: 'state', label: 'State' },
  { name: 'payment_terms', label: 'Payment terms', placeholder: 'e.g. Net 30 days' },
  {
    name: 'credit_days',
    label: 'Credit days',
    type: 'number',
    min: 0,
    placeholder: 'Sets the payment due date',
    validate: (v) => (Number(v) > 365 ? 'At most 365 days' : undefined),
  },
  ...(editing ? [{ name: 'status', label: 'Status', type: 'select', required: true, options: statuses }] : []),
]

export default function SuppliersPanel({ options, canManage, refreshKey, onChanged }) {
  const toast = useToast()
  const [editing, setEditing] = useState(null) // supplier row | {} for new
  const [viewing, setViewing] = useState(null)
  const [removing, setRemoving] = useState(null)
  const l = usePagedList(purchaseApi.listSuppliers, { status: '', state: '', ordering: 'name' }, refreshKey)
  const statuses = choiceOptions(options.data?.supplier_statuses)

  const save = async (values) => {
    const body = { ...values, credit_days: optionalNumber(values.credit_days) ?? null }
    const s = editing.id ? await purchaseApi.updateSupplier(editing.id, body) : await purchaseApi.createSupplier(body)
    toast.success(editing.id ? `${s.name} updated` : `Supplier ${s.name} added (${s.supplier_code})`)
    onChanged()
  }

  const remove = async () => {
    await purchaseApi.deleteSupplier(removing.id)
    toast.success(`${removing.name} deleted`)
    onChanged()
  }

  const columns = [
    { key: 'supplier_code', header: 'Supplier ID', render: (r) => <span className="nowrap">{r.supplier_code}</span> },
    { key: 'name', header: 'Supplier', render: (r) => <strong>{r.name}</strong> },
    { key: 'contact_person', header: 'Contact', render: (r) => dash(r.contact_person) },
    { key: 'phone', header: 'Phone', render: (r) => dash(r.phone) },
    { key: 'city', header: 'City / State', render: (r) => [r.city, r.state].filter(Boolean).join(', ') || '—' },
    { key: 'gstin', header: 'GSTIN', render: (r) => dash(r.gstin) },
    { key: 'payment_terms', header: 'Payment Terms', render: (r) => dash(r.payment_terms) },
    { key: 'purchase_value', header: 'Purchases', align: 'right', render: (r) => money(r.purchase_value) },
    { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
    {
      key: 'actions',
      sticky: true,
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      render: (r) => (
        <span className="row-actions">
          <Button size="sm" variant="ghost" icon={Eye} onClick={() => setViewing(r)} aria-label={`View ${r.name}`} />
          {canManage && <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setEditing(r)} aria-label={`Edit ${r.name}`} />}
          {canManage && <Button size="sm" variant="ghost" icon={Trash2} onClick={() => setRemoving(r)} aria-label={`Delete ${r.name}`} />}
        </span>
      ),
    },
  ]

  return (
    <Card
      title="Suppliers"
      subtitle="Everyone you buy raw materials and products from"
      bodyClassName="card__body--flush"
      action={canManage && <Button size="sm" icon={Plus} onClick={() => setEditing({})}>Add Supplier</Button>}
    >
      <ListToolbar
        search={l.search}
        onSearch={l.setSearch}
        searchLabel="Search name, GSTIN, city or contact"
        onFilter={l.setFilter}
        filters={[
          { name: 'status', label: 'Filter by status', value: l.filters.status, options: withAll('All statuses', statuses) },
          { name: 'ordering', label: 'Sort suppliers', value: l.filters.ordering, options: SORTS },
        ]}
      />
      {l.result.error && !l.result.loading ? (
        <div className="card__pad">
          <ErrorMessage message={l.result.error.message} onRetry={l.result.reload} />
        </div>
      ) : (
        <Table
          loading={l.result.loading}
          caption="Suppliers"
          data={l.rows}
          columns={columns}
          emptyIcon={Users}
          emptyTitle={l.filtered ? 'No suppliers match' : 'No suppliers yet'}
          emptyMessage={l.filtered ? 'Try another search or filter.' : 'Add your first supplier to start recording purchases.'}
          pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }}
        />
      )}

      <FormModal
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        title={editing?.id ? `Edit ${editing.name}` : 'Add Supplier'}
        subtitle={editing?.id ? editing.supplier_code : 'The supplier ID is assigned automatically'}
        submitLabel={editing?.id ? 'Save Changes' : 'Add Supplier'}
        initialValues={editing?.id ? { ...editing, credit_days: editing.credit_days ?? '' } : {}}
        fields={supplierFields(statuses, Boolean(editing?.id))}
        onSubmit={save}
      />
      <SupplierDetail supplier={viewing} onClose={() => setViewing(null)} />
      <ConfirmDialog
        open={Boolean(removing)}
        onClose={() => setRemoving(null)}
        onConfirm={remove}
        danger
        title="Delete supplier?"
        message={`${removing?.name ?? ''} will be deleted. Suppliers with purchases, payments or returns can't be deleted — set them to Inactive instead.`}
        confirmLabel="Delete"
      />
    </Card>
  )
}

function SupplierDetail({ supplier, onClose }) {
  const detail = useApi(() => (supplier ? purchaseApi.getSupplier(supplier.id) : Promise.resolve(null)), [supplier?.id])
  if (!supplier) return null
  const s = detail.data
  return (
    <Modal open onClose={onClose} title={supplier.name} subtitle={supplier.supplier_code} size="lg">
      {detail.error && !detail.loading ? (
        <ErrorMessage message={detail.error.message} onRetry={detail.reload} />
      ) : !s || detail.loading ? (
        <Loader label="Loading supplier…" />
      ) : (
        <div className="stack">
          <dl className="detail-grid">
            {[
              ['Company', s.company_name], ['Contact person', s.contact_person], ['Phone', s.phone], ['Email', s.email],
              ['Address', s.address], ['City', s.city], ['State', s.state], ['GSTIN', s.gstin], ['Payment terms', s.payment_terms],
              ['Credit days', s.credit_days], ['Status', s.status], ['Added', date(s.created_at)],
              ['Total purchases', money(s.purchase_value)], ['Outstanding', money(s.outstanding)],
            ].map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{dash(v)}</dd>
              </div>
            ))}
          </dl>
          <h3 className="card__title">Recent purchases</h3>
          <Table compact caption="Recent purchases" data={list(s.recent_purchases)} columns={PURCHASE_COLUMNS}
                 emptyTitle="No purchases from this supplier yet" emptyMessage="Purchases you record will be listed here." />
        </div>
      )}
    </Modal>
  )
}
