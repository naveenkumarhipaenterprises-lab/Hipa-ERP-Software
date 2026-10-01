import { inventoryApi } from '../../../api/inventoryApi'
import Badge from '../../../components/common/Badge'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import { useApi } from '../../../hooks/useApi'
import { formatDate, formatINR, formatKg } from '../../../utils/formatters'
import MovementList from './MovementList'

const show = (v, fmt) => (v === null || v === undefined || v === '' ? '—' : fmt ? fmt(v) : v)

/** One inventory item's figures plus its latest movements (GET /inventory/movements/?item=). */
export default function ItemDetailsModal({ item, onClose }) {
  if (!item) return null
  return <Details item={item} onClose={onClose} />
}

function Details({ item, onClose }) {
  const movements = useApi(() => inventoryApi.listMovements({ item: item.id, page_size: 10 }), [item.id])
  const rows = Array.isArray(movements.data?.results) ? movements.data.results : []

  return (
    <Modal open onClose={onClose} title={item.product} subtitle="Stock details and recent movements">
      <dl className="detail-list">
        <dt>Current stock</dt>
        <dd>{show(item.stock_kg, formatKg)}</dd>
        <dt>Minimum stock</dt>
        <dd>{show(item.min_stock_kg, formatKg)}</dd>
        <dt>Reorder level</dt>
        <dd>{show(item.reorder_level_kg, formatKg)}</dd>
        <dt>Value per kg</dt>
        <dd>{show(item.price_per_kg, formatINR)}</dd>
        <dt>Stock value</dt>
        <dd>{show(item.stock_value, formatINR)}</dd>
        <dt>Status</dt>
        <dd>{item.status ? <Badge>{item.status}</Badge> : '—'}</dd>
        <dt>Last updated</dt>
        <dd>{show(item.updated_at, formatDate)}</dd>
      </dl>

      <h3 className="modal__section-title">Recent movements</h3>
      {movements.loading ? (
        <Loader label="Loading movements…" />
      ) : movements.error ? (
        <ErrorMessage message={movements.error.message} onRetry={movements.reload} />
      ) : (
        <MovementList items={rows} showProduct={false} emptyMessage="No stock has been recorded in or out for this product yet." />
      )}
    </Modal>
  )
}
