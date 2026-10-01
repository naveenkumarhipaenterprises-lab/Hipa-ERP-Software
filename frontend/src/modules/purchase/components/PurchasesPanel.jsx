import { Ban, Eye, IndianRupee, PackageCheck, Pencil, Plus, ShoppingCart, Trash2, Undo2 } from 'lucide-react'
import { useState } from 'react'
import { purchaseApi } from '../../../api/purchaseApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import TotalsSummary from '../../../components/common/TotalsSummary'
import { useApi } from '../../../hooks/useApi'
import { usePagedList } from '../../../hooks/usePagedList'
import { useToast } from '../../../hooks/useToast'
import { choiceOptions, dash, date, idOptions, list, money, qty, withAll } from '../shared'
import ListToolbar from './ListToolbar'
import { PURCHASE_COLUMNS } from './purchaseColumns'

/**
 * Purchase transactions: list with search, status / payment / supplier filters and a date range,
 * plus view, edit, receive, pay, return, cancel and delete actions (each only where the backend allows it).
 */
export default function PurchasesPanel({ options, canManage, canPay, refreshKey, onChanged, onNew, onEdit, onReceive, onPay, onReturn }) {
  const toast = useToast()
  const [viewing, setViewing] = useState(null)
  const [confirm, setConfirm] = useState(null) // { kind: 'cancel' | 'delete', row }
  const l = usePagedList(purchaseApi.listPurchases, { status: '', payment_status: '', supplier: '', date_from: '', date_to: '' }, refreshKey)
  const o = options.data ?? {}

  const run = async () => {
    const { kind, row } = confirm
    if (kind === 'cancel') await purchaseApi.cancelPurchase(row.id)
    else await purchaseApi.deletePurchase(row.id)
    toast.success(`${row.purchase_number} ${kind === 'cancel' ? 'cancelled' : 'deleted'}`)
    onChanged()
  }

  const actions = (r) => (
    <span className="row-actions">
      <Button size="sm" variant="ghost" icon={Eye} onClick={() => setViewing(r)} aria-label={`View ${r.purchase_number}`} />
      {canManage && r.can_edit && <Button size="sm" variant="ghost" icon={Pencil} onClick={() => onEdit(r)} aria-label={`Edit ${r.purchase_number}`} />}
      {canManage && Number(r.pending_quantity) > 0 && r.status !== 'Cancelled' && (
        <Button size="sm" variant="ghost" icon={PackageCheck} onClick={() => onReceive(r)} aria-label={`Record goods receipt for ${r.purchase_number}`} />
      )}
      {canPay && Number(r.balance) > 0 && (
        <Button size="sm" variant="ghost" icon={IndianRupee} onClick={() => onPay(r)} aria-label={`Record payment for ${r.purchase_number}`} />
      )}
      {canManage && r.can_cancel && <Button size="sm" variant="ghost" icon={Ban} onClick={() => setConfirm({ kind: 'cancel', row: r })} aria-label={`Cancel ${r.purchase_number}`} />}
      {canManage && r.can_delete && <Button size="sm" variant="ghost" icon={Trash2} onClick={() => setConfirm({ kind: 'delete', row: r })} aria-label={`Delete ${r.purchase_number}`} />}
    </span>
  )

  const columns = [
    ...PURCHASE_COLUMNS,
    { key: 'balance', header: 'Balance', align: 'right', render: (r) => (r.status === 'Cancelled' ? '—' : money(r.balance)) },
    { key: 'actions', sticky: true, header: <span className="sr-only">Actions</span>, align: 'right', render: actions },
  ]

  return (
    <Card
      title="Purchase Transactions"
      subtitle="Subtotal − Discount + GST = Total"
      bodyClassName="card__body--flush"
      action={canManage && <Button size="sm" icon={Plus} onClick={onNew}>Record Purchase</Button>}
    >
      <ListToolbar
        search={l.search}
        onSearch={l.setSearch}
        searchLabel="Search purchase ID, supplier or item"
        onFilter={l.setFilter}
        filters={[
          { name: 'status', label: 'Filter by status', value: l.filters.status, options: withAll('All statuses', choiceOptions(o.purchase_statuses)) },
          { name: 'payment_status', label: 'Filter by payment', value: l.filters.payment_status, options: withAll('All payments', choiceOptions(o.payment_statuses)) },
          { name: 'supplier', label: 'Filter by supplier', value: l.filters.supplier, options: withAll('All suppliers', idOptions(o.suppliers)) },
        ]}
        dates={{ from: l.filters.date_from, to: l.filters.date_to, onChange: l.setFilter }}
      />
      {l.result.error && !l.result.loading ? (
        <div className="card__pad">
          <ErrorMessage message={l.result.error.message} onRetry={l.result.reload} />
        </div>
      ) : (
        <Table
          loading={l.result.loading}
          caption="Purchase transactions"
          data={l.rows}
          columns={columns}
          emptyIcon={ShoppingCart}
          emptyTitle={l.filtered ? 'No purchases match' : 'No purchases recorded yet'}
          emptyMessage={l.filtered ? 'Try another search, filter or date range.' : 'Purchases you record will be listed here.'}
          pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }}
        />
      )}

      <PurchaseDetail
        purchase={viewing}
        refreshKey={refreshKey}
        onClose={() => setViewing(null)}
        actions={{ canManage, canPay, onReceive, onPay, onReturn }}
      />
      <ConfirmDialog
        open={Boolean(confirm)}
        onClose={() => setConfirm(null)}
        onConfirm={run}
        danger
        title={confirm?.kind === 'cancel' ? 'Cancel purchase?' : 'Delete purchase?'}
        message={
          confirm?.kind === 'cancel'
            ? `${confirm?.row.purchase_number} will be marked Cancelled. It stays in the records.`
            : `${confirm?.row.purchase_number ?? ''} will be permanently deleted.`
        }
        confirmLabel={confirm?.kind === 'cancel' ? 'Cancel Purchase' : 'Delete'}
        cancelLabel="Keep"
      />
    </Card>
  )
}

function PurchaseDetail({ purchase, refreshKey, onClose, actions }) {
  const detail = useApi(() => (purchase ? purchaseApi.getPurchase(purchase.id) : Promise.resolve(null)), [purchase?.id, refreshKey])
  if (!purchase) return null
  const p = detail.data
  const open = p && p.status !== 'Cancelled'
  const footer = p && open && (
    <>
      {actions.canManage && Number(p.pending_quantity) > 0 && (
        <Button variant="outline" icon={PackageCheck} onClick={() => { onClose(); actions.onReceive(p) }}>Goods Receipt</Button>
      )}
      {actions.canManage && Number(p.received_quantity) > 0 && (
        <Button variant="outline" icon={Undo2} onClick={() => { onClose(); actions.onReturn(p) }}>Return</Button>
      )}
      {actions.canPay && Number(p.balance) > 0 && (
        <Button icon={IndianRupee} onClick={() => { onClose(); actions.onPay(p) }}>Record Payment</Button>
      )}
    </>
  )
  return (
    <Modal open onClose={onClose} title={purchase.purchase_number} subtitle={`${purchase.supplier} · ${purchase.item}`} size="lg" footer={footer || undefined}>
      {detail.error && !detail.loading ? (
        <ErrorMessage message={detail.error.message} onRetry={detail.reload} />
      ) : !p ? (
        <Loader label="Loading purchase…" />
      ) : (
        <div className="stack">
          <dl className="detail-grid">
            {[
              ['Status', <Badge key="s">{p.status}</Badge>], ['Payment', p.payment_status ? <Badge key="p">{p.payment_status}</Badge> : '—'],
              ['Purchase date', date(p.purchase_date)], ['Expected receipt', date(p.expected_receipt_date)], ['Payment due', date(p.payment_due_date)],
              ['Quantity', qty(p.quantity, p.unit)], ['Received', qty(p.received_quantity, p.unit)], ['Still to receive', qty(p.pending_quantity, p.unit)],
              ['Unit price', money(p.unit_price)], ['Discount', `${p.discount_pct}%`], ['GST / Tax', `${p.gst_pct}%`],
              ['Paid', money(p.paid_amount)], ['Returned (credited)', money(p.returned_amount)], ['Balance', money(p.balance)],
            ].map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
          <TotalsSummary totals={{ subtotal: p.subtotal, discount: p.discount_amount, gst: p.gst_amount, total: p.total_amount }} />
          {p.notes && <p><strong>Notes:</strong> {p.notes}</p>}
          <h3 className="card__title">Goods receipts</h3>
          <Table compact caption="Goods receipts" data={list(p.goods_receipts)} emptyTitle="Nothing received yet" emptyMessage="Goods receipts (GRN) will be listed here."
                 columns={[
                   { key: 'grn_number', header: 'GRN' }, { key: 'received_date', header: 'Date', render: (r) => date(r.received_date) },
                   { key: 'received_quantity', header: 'Received', align: 'right', render: (r) => qty(r.received_quantity, r.unit) },
                   { key: 'damaged_quantity', header: 'Damaged', align: 'right', render: (r) => qty(r.damaged_quantity, r.unit) },
                   { key: 'accepted_quantity', header: 'Accepted', align: 'right', render: (r) => qty(r.accepted_quantity, r.unit) },
                   { key: 'quality_status', header: 'Quality', render: (r) => <Badge>{r.quality_status}</Badge> },
                 ]} />
          <h3 className="card__title">Payments</h3>
          <Table compact caption="Payments" data={list(p.payments)} emptyTitle="No payments yet" emptyMessage="Supplier payments for this purchase will be listed here."
                 columns={[
                   { key: 'payment_number', header: 'Payment ID' }, { key: 'payment_date', header: 'Date', render: (r) => date(r.payment_date) },
                   { key: 'amount', header: 'Amount', align: 'right', render: (r) => money(r.amount) },
                   { key: 'payment_method', header: 'Method' }, { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
                 ]} />
          {list(p.returns).length > 0 && (
            <>
              <h3 className="card__title">Returns</h3>
              <Table compact caption="Returns" data={p.returns}
                     columns={[
                       { key: 'return_number', header: 'Return ID' }, { key: 'return_date', header: 'Date', render: (r) => date(r.return_date) },
                       { key: 'quantity', header: 'Quantity', align: 'right', render: (r) => qty(r.quantity, r.unit) },
                       { key: 'amount', header: 'Amount', align: 'right', render: (r) => money(r.amount) },
                       { key: 'reason', header: 'Reason', render: (r) => dash(r.reason) }, { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
                     ]} />
            </>
          )}
        </div>
      )}
    </Modal>
  )
}
