import { CircleCheck, IndianRupee, PackageCheck, Plus, Trash2, Undo2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { purchaseApi } from '../../../api/purchaseApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Table from '../../../components/common/Table'
import { usePagedList } from '../../../hooks/usePagedList'
import { useToast } from '../../../hooks/useToast'
import { choiceOptions, dash, date, idOptions, money, qty, withAll } from '../shared'
import ListToolbar from './ListToolbar'

function ListBody({ l, caption, columns, icon, emptyTitle, emptyMessage }) {
  if (l.result.error && !l.result.loading)
    return (
      <div className="card__pad">
        <ErrorMessage message={l.result.error.message} onRetry={l.result.reload} />
      </div>
    )
  return (
    <Table
      loading={l.result.loading}
      caption={caption}
      data={l.rows}
      columns={columns}
      emptyIcon={icon}
      emptyTitle={l.filtered ? `No ${caption.toLowerCase()} match` : emptyTitle}
      emptyMessage={l.filtered ? 'Try another search, filter or date range.' : emptyMessage}
      pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }}
    />
  )
}

/** Goods receipts (GRN). Only the accepted quantity goes into stock. Not a purchase order. */
export function ReceiptsPanel({ options, canManage, refreshKey, onNew }) {
  const o = options.data ?? {}
  const l = usePagedList(purchaseApi.listGoodsReceipts, { quality_status: '', supplier: '', date_from: '', date_to: '' }, refreshKey)
  return (
    <Card title="Goods Receipts (GRN)" subtitle="Goods received against purchases" bodyClassName="card__body--flush"
          action={canManage && <Button size="sm" icon={Plus} onClick={onNew}>Record Receipt</Button>}>
      <ListToolbar
        search={l.search} onSearch={l.setSearch} searchLabel="Search GRN, purchase, supplier or item" onFilter={l.setFilter}
        filters={[
          { name: 'quality_status', label: 'Filter by quality status', value: l.filters.quality_status, options: withAll('All quality statuses', choiceOptions(o.quality_statuses)) },
          { name: 'supplier', label: 'Filter by supplier', value: l.filters.supplier, options: withAll('All suppliers', idOptions(o.suppliers)) },
        ]}
        dates={{ from: l.filters.date_from, to: l.filters.date_to, onChange: l.setFilter }}
      />
      <ListBody l={l} caption="Goods receipts" icon={PackageCheck} emptyTitle="No goods received yet" emptyMessage="Record a goods receipt when a purchase arrives."
        columns={[
          { key: 'grn_number', header: 'GRN Number', render: (r) => <strong className="nowrap">{r.grn_number}</strong> },
          { key: 'purchase_number', header: 'Purchase Ref.', render: (r) => <span className="nowrap">{r.purchase_number}</span> },
          { key: 'supplier', header: 'Supplier' },
          { key: 'received_date', header: 'Received', render: (r) => <span className="nowrap">{date(r.received_date)}</span> },
          { key: 'item', header: 'Material / Product' },
          { key: 'received_quantity', header: 'Received', align: 'right', render: (r) => qty(r.received_quantity, r.unit) },
          { key: 'damaged_quantity', header: 'Damaged', align: 'right', render: (r) => qty(r.damaged_quantity, r.unit) },
          { key: 'accepted_quantity', header: 'Accepted', align: 'right', render: (r) => qty(r.accepted_quantity, r.unit) },
          { key: 'quality_status', header: 'Quality', render: (r) => <Badge>{r.quality_status}</Badge> },
          { key: 'remarks', header: 'Remarks', render: (r) => dash(r.remarks) },
        ]} />
    </Card>
  )
}

/** Goods returned to suppliers; Pending → Completed (credited against the purchase) or Cancelled (stock back in). */
export function ReturnsPanel({ options, canManage, refreshKey, onNew, onChanged }) {
  const toast = useToast()
  const o = options.data ?? {}
  const [confirm, setConfirm] = useState(null) // { row, status }
  const l = usePagedList(purchaseApi.listReturns, { status: '', reason: '', supplier: '', date_from: '', date_to: '' }, refreshKey)
  const apply = async () => {
    await purchaseApi.setReturnStatus(confirm.row.id, confirm.status)
    toast.success(`${confirm.row.return_number} marked ${confirm.status}`)
    onChanged()
  }
  return (
    <Card title="Purchase Returns" subtitle="Goods sent back to suppliers" bodyClassName="card__body--flush"
          action={canManage && <Button size="sm" icon={Plus} onClick={onNew}>Record Return</Button>}>
      <ListToolbar
        search={l.search} onSearch={l.setSearch} searchLabel="Search return ID, supplier or item" onFilter={l.setFilter}
        filters={[
          { name: 'status', label: 'Filter by status', value: l.filters.status, options: withAll('All statuses', choiceOptions(o.return_statuses)) },
          { name: 'reason', label: 'Filter by reason', value: l.filters.reason, options: withAll('All reasons', choiceOptions(o.return_reasons)) },
          { name: 'supplier', label: 'Filter by supplier', value: l.filters.supplier, options: withAll('All suppliers', idOptions(o.suppliers)) },
        ]}
        dates={{ from: l.filters.date_from, to: l.filters.date_to, onChange: l.setFilter }}
      />
      <ListBody l={l} caption="Purchase returns" icon={Undo2} emptyTitle="No purchase returns" emptyMessage="Goods returned to suppliers will be listed here."
        columns={[
          { key: 'return_number', header: 'Return ID', render: (r) => <strong className="nowrap">{r.return_number}</strong> },
          { key: 'supplier', header: 'Supplier' },
          { key: 'item', header: 'Material / Product' },
          { key: 'quantity', header: 'Quantity', align: 'right', render: (r) => qty(r.quantity, r.unit) },
          { key: 'return_date', header: 'Return Date', render: (r) => <span className="nowrap">{date(r.return_date)}</span> },
          { key: 'reason', header: 'Reason' },
          { key: 'amount', header: 'Amount', align: 'right', render: (r) => money(r.amount) },
          { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
          { key: 'remarks', header: 'Remarks', render: (r) => dash(r.remarks) },
          {
            key: 'actions', sticky: true, header: <span className="sr-only">Actions</span>, align: 'right',
            render: (r) => canManage && r.can_update && (
              <span className="row-actions">
                <Button size="sm" variant="ghost" icon={CircleCheck} onClick={() => setConfirm({ row: r, status: 'completed' })} aria-label={`Mark ${r.return_number} completed`} />
                <Button size="sm" variant="ghost" icon={XCircle} onClick={() => setConfirm({ row: r, status: 'cancelled' })} aria-label={`Cancel ${r.return_number}`} />
              </span>
            ),
          },
        ]} />
      <ConfirmDialog
        open={Boolean(confirm)}
        onClose={() => setConfirm(null)}
        onConfirm={apply}
        danger={confirm?.status === 'cancelled'}
        title={confirm?.status === 'completed' ? 'Mark return completed?' : 'Cancel return?'}
        message={
          confirm?.status === 'completed'
            ? `The supplier has credited ${money(confirm?.row.amount)}. It will reduce the amount payable on the purchase.`
            : 'The goods will be added back to stock.'
        }
        confirmLabel={confirm?.status === 'completed' ? 'Mark Completed' : 'Cancel Return'}
        cancelLabel="Keep"
      />
    </Card>
  )
}

/** Supplier payments: Pending (scheduled), Overdue (scheduled and past its date), Partially Paid, Paid. */
export function PaymentsPanel({ options, canPay, refreshKey, onNew, onChanged }) {
  const toast = useToast()
  const o = options.data ?? {}
  const [confirm, setConfirm] = useState(null) // { row, kind: 'pay' | 'delete' }
  const l = usePagedList(purchaseApi.listPayments, { status: '', payment_method: '', supplier: '', date_from: '', date_to: '' }, refreshKey)
  const apply = async () => {
    if (confirm.kind === 'pay') await purchaseApi.markPaymentPaid(confirm.row.id, {})
    else await purchaseApi.deletePayment(confirm.row.id)
    toast.success(`${confirm.row.payment_number} ${confirm.kind === 'pay' ? 'recorded as paid' : 'deleted'}`)
    onChanged()
  }
  return (
    <Card title="Supplier Payments" subtitle="Money paid, or scheduled to be paid, to suppliers" bodyClassName="card__body--flush"
          action={canPay && <Button size="sm" icon={Plus} onClick={onNew}>Record Payment</Button>}>
      <ListToolbar
        search={l.search} onSearch={l.setSearch} searchLabel="Search payment ID, supplier or reference" onFilter={l.setFilter}
        filters={[
          { name: 'status', label: 'Filter by status', value: l.filters.status, options: withAll('All statuses', choiceOptions(o.supplier_payment_statuses)) },
          { name: 'payment_method', label: 'Filter by method', value: l.filters.payment_method, options: withAll('All methods', choiceOptions(o.payment_methods)) },
          { name: 'supplier', label: 'Filter by supplier', value: l.filters.supplier, options: withAll('All suppliers', idOptions(o.suppliers)) },
        ]}
        dates={{ from: l.filters.date_from, to: l.filters.date_to, onChange: l.setFilter }}
      />
      <ListBody l={l} caption="Supplier payments" icon={IndianRupee} emptyTitle="No supplier payments yet" emptyMessage="Payments you make to suppliers will be listed here."
        columns={[
          { key: 'payment_number', header: 'Payment ID', render: (r) => <strong className="nowrap">{r.payment_number}</strong> },
          { key: 'supplier', header: 'Supplier' },
          { key: 'purchase_number', header: 'Purchase Ref.', render: (r) => dash(r.purchase_number) },
          { key: 'amount', header: 'Amount', align: 'right', render: (r) => money(r.amount) },
          { key: 'payment_date', header: 'Payment Date', render: (r) => <span className="nowrap">{date(r.payment_date)}</span> },
          { key: 'payment_method', header: 'Method' },
          { key: 'transaction_reference', header: 'Transaction Ref.', render: (r) => dash(r.transaction_reference) },
          { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
          {
            key: 'actions', sticky: true, header: <span className="sr-only">Actions</span>, align: 'right',
            render: (r) => canPay && r.can_mark_paid && (
              <span className="row-actions">
                <Button size="sm" variant="ghost" icon={CircleCheck} onClick={() => setConfirm({ row: r, kind: 'pay' })} aria-label={`Mark ${r.payment_number} paid`} />
                <Button size="sm" variant="ghost" icon={Trash2} onClick={() => setConfirm({ row: r, kind: 'delete' })} aria-label={`Delete ${r.payment_number}`} />
              </span>
            ),
          },
        ]} />
      <ConfirmDialog
        open={Boolean(confirm)}
        onClose={() => setConfirm(null)}
        onConfirm={apply}
        danger={confirm?.kind === 'delete'}
        title={confirm?.kind === 'pay' ? 'Record as paid today?' : 'Delete scheduled payment?'}
        message={confirm?.kind === 'pay' ? `${money(confirm?.row.amount)} to ${confirm?.row.supplier} will be recorded as paid today.` : 'This scheduled payment will be removed.'}
        confirmLabel={confirm?.kind === 'pay' ? 'Mark Paid' : 'Delete'}
        cancelLabel="Keep"
      />
    </Card>
  )
}
