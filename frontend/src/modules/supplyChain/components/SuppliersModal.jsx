import { Plus, Search, Users } from 'lucide-react'
import { useState } from 'react'
import { supplyChainApi } from '../../../api/supplyChainApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { useToast } from '../../../hooks/useToast'
import { formatPercent } from '../../../utils/formatters'

const PAGE_SIZE = 10
const pct = (v) => (v === null || v === undefined || v === '' ? '—' : formatPercent(v, 0))

const SUPPLIER_FIELDS = [
  { name: 'name', label: 'Supplier name', required: true, full: true, placeholder: 'Business name' },
  { name: 'city', label: 'City', required: true, placeholder: 'City or town' },
  { name: 'contact_person', label: 'Contact person', placeholder: 'Name of the main contact' },
  { name: 'phone', label: 'Mobile number', type: 'tel', placeholder: '10-digit mobile number' },
  { name: 'email', label: 'Email', type: 'email', placeholder: 'name@supplier.com' },
]

/** Supplier list (GET /supply-chain/suppliers/) with Add Supplier for allowed roles. */
export default function SuppliersModal({ open, canManage, onClose, onChanged }) {
  if (!open) return null
  return <Suppliers canManage={canManage} onClose={onClose} onChanged={onChanged} />
}

function Suppliers({ canManage, onClose, onChanged }) {
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [adding, setAdding] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(query)
  const suppliers = useApi(() => supplyChainApi.listSuppliers({ page, page_size: PAGE_SIZE, search: query }), [page, query, refreshKey])
  const rows = Array.isArray(suppliers.data?.results) ? suppliers.data.results : []
  const total = Number(suppliers.data?.count) || 0

  const addSupplier = async (values) => {
    const body = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, typeof v === 'string' ? v.trim() : v]))
    if (body.phone) body.phone = body.phone.replace(/[\s-]/g, '')
    const created = await supplyChainApi.createSupplier(body)
    toast.success(`${created?.name ?? body.name} added`)
    setRefreshKey((k) => k + 1)
    onChanged?.()
  }

  // The add form replaces this dialog while open, so only one modal traps focus at a time
  if (adding) {
    return (
      <FormModal
        open
        onClose={() => setAdding(false)}
        title="Add Supplier"
        subtitle="Create a new supplier record"
        fields={SUPPLIER_FIELDS}
        submitLabel="Add Supplier"
        onSubmit={addSupplier}
      />
    )
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Suppliers"
      subtitle="Supplier list and performance scores"
      size="lg"
      footer={
        canManage && (
          <Button icon={Plus} onClick={() => setAdding(true)}>
            Add Supplier
          </Button>
        )
      }
    >
      <div className="toolbar toolbar--flush">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search supplier or city" aria-label="Search suppliers" />
        </label>
      </div>
      {suppliers.error && !suppliers.loading ? (
        <ErrorMessage message={suppliers.error.message} onRetry={suppliers.reload} />
      ) : (
        <Table
          compact
          loading={suppliers.loading}
          caption="Suppliers"
          data={rows}
          emptyIcon={Users}
          emptyTitle={query ? 'No suppliers match your search' : 'No suppliers yet'}
          emptyMessage={query ? 'Try a different search.' : 'Add your first supplier to start raising purchase orders.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
          columns={[
            { key: 'name', header: 'Supplier', render: (r) => <strong>{r.name}</strong> },
            { key: 'city', header: 'City', render: (r) => r.city || '—' },
            { key: 'phone', header: 'Phone', render: (r) => r.phone || '—' },
            { key: 'quality_pct', header: 'Quality', align: 'right', render: (r) => pct(r.quality_pct) },
            { key: 'on_time_pct', header: 'On-Time', align: 'right', render: (r) => pct(r.on_time_pct) },
            { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
          ]}
        />
      )}
    </Modal>
  )
}
