import { CircleCheck, Clock, Link2, Pencil, Search, Truck } from 'lucide-react'
import { useState } from 'react'
import { supplyChainApi } from '../../../api/supplyChainApi'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import { Select } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { useToast } from '../../../hooks/useToast'
import { LinkPurchaseModal, ShipmentStatusModal } from './ShipmentForms'
import { SHIPMENT_COLUMNS } from './shipmentColumns'
import DeleteRecordButton from '../../../components/common/DeleteRecordButton'

const PAGE_SIZE = 10

/**
 * All shipments with search, status filter and server pagination; managers can update their status and link a
 * shipment saved without a purchase to its purchase.
 */
export default function ShipmentsModal({ open, statuses, canManage, onChanged, onClose }) {
  if (!open) return null
  return <Shipments statuses={statuses} canManage={canManage} onChanged={onChanged} onClose={onClose} />
}

function Shipments({ statuses, canManage, onChanged, onClose }) {
  const toast = useToast()
  const [change, setChange] = useState(null) // { shipment, status }
  const [linking, setLinking] = useState(null) // shipment
  const [editing, setEditing] = useState(null) // shipment
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

  const linkPurchase = async (purchaseId) => {
    const s = await supplyChainApi.linkPurchase(linking.id, purchaseId)
    toast.success(`${s.shipment_number} linked to ${s.purchase_number}`)
    shipments.reload()
    onChanged?.()
  }

  const saveEdit = async (values) => {
    const s = await supplyChainApi.updateShipment(editing.id, values)
    toast.success(`${s.shipment_number} updated`)
    shipments.reload()
    onChanged?.()
  }

  const columns = [...SHIPMENT_COLUMNS, {
        key: 'actions', sticky: true, align: 'right', header: <span className="sr-only">Actions</span>,
        render: (r) => (
          <span className="row-actions">
            {canManage && r.can_update && (
              <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setEditing(r)} aria-label={`Edit ${r.shipment_number}`} />
            )}
            {canManage && r.can_link_purchase && (
              <Button size="sm" variant="ghost" icon={Link2} onClick={() => setLinking(r)} aria-label={`Link ${r.shipment_number} to a purchase`} />
            )}
            {canManage && r.can_update && (r.status === 'Delayed' ? (
              <Button size="sm" variant="ghost" icon={Truck} onClick={() => setChange({ shipment: r, status: 'in_transit' })} aria-label={`Mark ${r.shipment_number} in transit`} />
            ) : (
              <Button size="sm" variant="ghost" icon={Clock} onClick={() => setChange({ shipment: r, status: 'delayed' })} aria-label={`Mark ${r.shipment_number} delayed`} />
            ))}
            {canManage && r.can_update && (
              <Button size="sm" variant="soft" icon={CircleCheck} onClick={() => setChange({ shipment: r, status: 'delivered' })} aria-label={`Mark ${r.shipment_number} delivered`}>Delivered</Button>
            )}
            <DeleteRecordButton kind="shipment" id={r.id} label={r.shipment_number} onDeleted={() => { shipments.reload(); onChanged?.() }} />
          </span>
        ),
      }]

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
      <LinkPurchaseModal shipment={linking} onClose={() => setLinking(null)} onSubmit={linkPurchase} />
      <FormModal
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        title={editing ? `Edit ${editing.shipment_number}` : ''}
        subtitle={editing ? `${editing.item} from ${editing.supplier}. Supplier, item and purchase stay as recorded.` : ''}
        initialValues={editing ? { quantity: editing.quantity, destination: editing.destination, dispatched_on: editing.dispatched_on,
                                   eta: editing.eta } : {}}
        fields={[
          { name: 'quantity', label: `Quantity${editing?.unit ? ` (${editing.unit})` : ''}`, type: 'number', required: true, min: 0.001 },
          { name: 'destination', label: 'Destination', required: true },
          { name: 'dispatched_on', label: 'Dispatched on', type: 'date', required: true },
          { name: 'eta', label: 'Expected arrival', type: 'date', required: true },
        ]}
        submitLabel="Save"
        onSubmit={saveEdit}
      />
    </Modal>
  )
}
