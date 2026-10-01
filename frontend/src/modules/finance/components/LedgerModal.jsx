import { Receipt, Search } from 'lucide-react'
import { useState } from 'react'
import { financeApi } from '../../../api/financeApi'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { transactionColumns } from './transactionColumns'

const PAGE_SIZE = 10
const TYPES = [
  { value: '', label: 'All types' },
  { value: 'income', label: 'Income' },
  { value: 'expense', label: 'Expense' },
]

/** Full transaction ledger: search, type/status filters and server pagination. */
export default function LedgerModal({ open, statuses, refreshKey, onClose, onView }) {
  if (!open) return null
  return <Ledger statuses={statuses} refreshKey={refreshKey} onClose={onClose} onView={onView} />
}

function Ledger({ statuses, refreshKey, onClose, onView }) {
  const [search, setSearch] = useState('')
  const [type, setType] = useState('')
  const [status, setStatus] = useState('')
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(JSON.stringify([query, type, status]))
  const txs = useApi(() => financeApi.listTransactions({ page, page_size: PAGE_SIZE, search: query, type, status }), [page, query, type, status, refreshKey])
  const rows = Array.isArray(txs.data?.results) ? txs.data.results : []
  const total = Number(txs.data?.count) || 0
  const filtered = Boolean(query || type || status)

  return (
    <Modal open onClose={onClose} title="Transactions" subtitle="Full ledger" size="lg">
      <div className="toolbar toolbar--flush">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search description or reference" aria-label="Search transactions" />
        </label>
        <Select className="field--inline" aria-label="Filter by type" value={type} onChange={(e) => setType(e.target.value)} options={TYPES} />
        {Array.isArray(statuses) && statuses.length > 0 && (
          <Select
            className="field--inline"
            aria-label="Filter by status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            options={[{ value: '', label: 'All statuses' }, ...statuses]}
          />
        )}
      </div>
      {txs.error && !txs.loading ? (
        <ErrorMessage message={txs.error.message} onRetry={txs.reload} />
      ) : (
        <Table
          compact
          loading={txs.loading}
          caption="Transactions"
          data={rows}
          columns={transactionColumns(onView)}
          emptyIcon={Receipt}
          emptyTitle={filtered ? 'No transactions match your filters' : 'No transactions yet'}
          emptyMessage={filtered ? 'Try a different search or filter.' : 'Recorded income and expenses will be listed here.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
        />
      )}
    </Modal>
  )
}
