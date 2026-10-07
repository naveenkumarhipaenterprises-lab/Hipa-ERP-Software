import { CircleCheck, Clock, Search, Truck } from 'lucide-react'
import { useState } from 'react'
import { supplyChainApi } from '../../../api/supplyChainApi'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { useToast } from '../../../hooks/useToast'
import { ShipmentStatusModal } from './ShipmentForms'
import { SHIPMENT_COLUMNS } from './shipmentColumns'

const PAGE_SIZE = 10

/** All shipments with search, status filter and server pagination; managers can update their status. */
export default function ShipmentsModal({ open, statuses, canManage, onChanged, onClose }) {
  if (!open) return null
  return <Shipments statuses={statuses} canManage={canManage} onChanged={onChanged} onClose={onClose} />
}

function Shipments({ statuses, canManage, onChanged, onClose }) {
  const toast = useToast()
  const [change, setChange] = useState(null) // { shipment, status }
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(JSON.stringify([query, status]))
  const shipments = useApi(() => supplyChainApi.listShipments({ page, page_size: PAGE_SIZE, search: query, status }), [page, query, status])
  const rows = Array.isArray(shipments.data?.results) ? shipments.data.results : []
  const total = Number(shipments.data?.count) || 0

  const updateStatus = async (body) => {
    const s = await supplyChainApi.setShipmentStatus(change.shipment.id, body)
    toast.success(`${s?.shipment_number ?? change.shipment.shipment_number} marked ${s?.status ?? body.status}`)
    shipments.reload()
    onChanged?.()
  }

  const columns = canManage
    ? [...SHIPMENT_COLUMNS, {
        key: 'actions', sticky: true, align: 'right', header: <span className="sr-only">Actions</span>,
        render: (r) => r.can_update && (
          <span className="row-actions">
            {r.status === 'Delayed' ? (
              <Button size="sm" variant="ghost" icon={Truck} onClick={() => setChange({ shipment: r, status: 'in_transit' })} aria-label={`Mark ${r.shipment_number} in transit`} />
            ) : (
              <Button size="sm" variant="ghost" icon={Clock} onClick={() => setChange({ shipment: r, status: 'delayed' })} aria-label={`Mark ${r.shipment_number} delayed`} />
            )}
            <Button size="sm" variant="soft" icon={CircleCheck} onClick={() => setChange({ shipment: r, status: 'delivered' })} aria-label={`Mark ${r.shipment_number} delivered`}>Delivered</Button>
          </span>
        ),
      }]
    : SHIPMENT_COLUMNS

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
          columns={columns}
          emptyIcon={Truck}
          emptyTitle={query || status ? 'No shipments match your filters' : 'No shipments yet'}
          emptyMessage={query || status ? 'Try a different search or status.' : 'Shipments appear here once suppliers dispatch orders.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
        />
      )}
      <ShipmentStatusModal change={change} onClose={() => setChange(null)} onSubmit={updateStatus} />
    </Modal>
  )
}
