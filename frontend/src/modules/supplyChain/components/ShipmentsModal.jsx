import { Search, Truck } from 'lucide-react'
import { useState } from 'react'
import { supplyChainApi } from '../../../api/supplyChainApi'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { SHIPMENT_COLUMNS } from './shipmentColumns'

const PAGE_SIZE = 10

/** All shipments with search, status filter and server pagination (GET /supply-chain/shipments/). */
export default function ShipmentsModal({ open, statuses, onClose }) {
  if (!open) return null
  return <Shipments statuses={statuses} onClose={onClose} />
}

function Shipments({ statuses, onClose }) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(JSON.stringify([query, status]))
  const shipments = useApi(() => supplyChainApi.listShipments({ page, page_size: PAGE_SIZE, search: query, status }), [page, query, status])
  const rows = Array.isArray(shipments.data?.results) ? shipments.data.results : []
  const total = Number(shipments.data?.count) || 0

  return (
    <Modal open onClose={onClose} title="Shipment Tracking" subtitle="All shipments" size="lg">
      <div className="toolbar toolbar--flush">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search shipment ID or supplier" aria-label="Search shipments" />
        </label>
        <Select
          className="field--inline"
          aria-label="Filter by status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[{ value: '', label: 'All statuses' }, ...(Array.isArray(statuses) ? statuses : [])]}
        />
      </div>
      {shipments.error && !shipments.loading ? (
        <ErrorMessage message={shipments.error.message} onRetry={shipments.reload} />
      ) : (
        <Table
          compact
          loading={shipments.loading}
          caption="Shipments"
          data={rows}
          columns={SHIPMENT_COLUMNS}
          emptyIcon={Truck}
          emptyTitle={query || status ? 'No shipments match your filters' : 'No shipments yet'}
          emptyMessage={query || status ? 'Try a different search or status.' : 'Shipments appear here once suppliers dispatch orders.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
        />
      )}
    </Modal>
  )
}
