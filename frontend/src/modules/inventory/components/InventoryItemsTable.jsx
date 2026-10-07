import { Eye, Package, Pencil, Search } from 'lucide-react'
import { useState } from 'react'
import { inventoryApi } from '../../../api/inventoryApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import { Select } from '../../../components/common/Input'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatINR, formatNumber } from '../../../utils/formatters'
import ItemDetailsModal from './ItemDetailsModal'

const PAGE_SIZE = 10
const has = (v) => v !== null && v !== undefined && v !== ''
const kg = (v) => (has(v) ? formatNumber(v) : '—')

const ACTIVE_OPTIONS = [
  { value: 'true', label: 'Active products' },
  { value: 'false', label: 'Switched-off products' },
]

// Stock is not here: it only changes through Stock In / Stock Out, orders and returns
const EDIT_FIELDS = [
  { name: 'product_name', label: 'Product name', required: true, full: true },
  { name: 'price_per_kg', label: 'Value per kg (₹)', type: 'number', min: 0, required: true },
  { name: 'min_stock_kg', label: 'Minimum stock (kg)', type: 'number', min: 0, required: true },
  { name: 'reorder_level_kg', label: 'Reorder level (kg)', type: 'number', min: 0, required: true },
  {
    name: 'is_active', label: 'Status', type: 'select', required: true, full: true,
    options: [{ value: 'true', label: 'Active (can be sold and stocked)' }, { value: 'false', label: 'Switched off (hidden from new orders and stock entries)' }],
  },
]

/** Product inventory list: server-side search, status filter and pagination, with a details view and editing. */
export default function InventoryItemsTable({ refreshKey, statuses, canManage, onChanged }) {
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [viewing, setViewing] = useState(null)
  const [editing, setEditing] = useState(null)
  const [active, setActive] = useState('true')
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(JSON.stringify([query, status, active]))

  const items = useApi(() => inventoryApi.listItems({ page, page_size: PAGE_SIZE, search: query, status, active }), [page, query, status, active, refreshKey])
  const rows = Array.isArray(items.data?.results) ? items.data.results : []
  const total = Number(items.data?.count) || 0
  const filtered = Boolean(query || status)

  const save = async (values) => {
    const updated = await inventoryApi.updateItem(editing.id, {
      ...values,
      product_name: values.product_name.trim(),
      is_active: values.is_active === 'true',
    })
    toast.success(`${updated?.product ?? values.product_name.trim()} updated`)
    if (onChanged) onChanged()
    else items.reload()
  }

  return (
    <Card
      title="Product Inventory Details"
      subtitle={items.loading ? undefined : `${formatNumber(total)} product${total === 1 ? '' : 's'}`}
      bodyClassName="card__body--flush"
    >
      <div className="toolbar">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search products" aria-label="Search products" />
        </label>
        <Select
          className="field--inline"
          aria-label="Filter by stock status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[{ value: '', label: 'All statuses' }, ...(Array.isArray(statuses) ? statuses : [])]}
        />
        <Select className="field--inline" aria-label="Active or switched-off products" value={active} onChange={(e) => setActive(e.target.value)} options={ACTIVE_OPTIONS} />
      </div>

      {items.error && !items.loading ? (
        <div className="card__pad">
          <ErrorMessage message={items.error.message} onRetry={items.reload} />
        </div>
      ) : (
        <Table
          loading={items.loading}
          caption="Product inventory"
          data={rows}
          emptyIcon={Package}
          emptyTitle={filtered ? 'No products match your filters' : active === 'false' ? 'No switched-off products' : 'No products in inventory'}
          emptyMessage={filtered ? 'Try a different search or status.' : 'Products appear here once they are added.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
          columns={[
            { key: 'product', header: 'Product', render: (r) => <strong>{r.product}</strong> },
            { key: 'stock_kg', header: 'Stock (kg)', align: 'right', render: (r) => kg(r.stock_kg) },
            { key: 'min_stock_kg', header: 'Min (kg)', align: 'right', render: (r) => kg(r.min_stock_kg) },
            { key: 'reorder_level_kg', header: 'Reorder (kg)', align: 'right', render: (r) => kg(r.reorder_level_kg) },
            { key: 'stock_value', header: 'Stock Value', align: 'right', render: (r) => (has(r.stock_value) ? formatINR(r.stock_value) : '—') },
            { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
            { key: 'updated_at', header: 'Last Updated', render: (r) => (r.updated_at ? formatDate(r.updated_at) : '—') },
            {
              key: 'view',
              sticky: true,
              header: <span className="sr-only">Details</span>,
              align: 'right',
              render: (r) => (
                <span className="row-actions">
                  {canManage && <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setEditing(r)} aria-label={`Edit ${r.product}`} />}
                  <Button size="sm" variant="soft" icon={Eye} onClick={() => setViewing(r)} aria-label={`View ${r.product}`}>
                    View
                  </Button>
                </span>
              ),
            },
          ]}
        />
      )}

      <ItemDetailsModal item={viewing} onClose={() => setViewing(null)} />
      <FormModal
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        title={editing ? `Edit ${editing.product}` : 'Edit Product'}
        subtitle="Stock changes through Stock In and Stock Out, not here"
        fields={EDIT_FIELDS}
        initialValues={editing ? {
          product_name: editing.product, price_per_kg: editing.price_per_kg, min_stock_kg: editing.min_stock_kg,
          reorder_level_kg: editing.reorder_level_kg, is_active: String(editing.is_active !== false),
        } : undefined}
        submitLabel="Save Changes"
        onSubmit={save}
      />
    </Card>
  )
}
