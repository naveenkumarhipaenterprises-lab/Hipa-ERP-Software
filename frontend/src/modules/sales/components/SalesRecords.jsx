import { CircleCheck, IndianRupee, Plus, Undo2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { salesApi } from '../../../api/salesApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import EmptyState from '../../../components/common/EmptyState'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import ListToolbar from '../../../components/common/ListToolbar'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { usePagedList } from '../../../hooks/usePagedList'
import { useToast } from '../../../hooks/useToast'
import { choiceOptions, dash, date, list, money, optionalNumber, optionalText, withAll } from '../../../utils/display'
import { todayISO } from '../../../utils/formatters'

const notFuture = (v) => (v > todayISO() ? "Can't be in the future" : undefined)

function ListBody({ l, caption, columns, icon, emptyTitle, emptyMessage }) {
  if (l.result.error && !l.result.loading)
    return <div className="card__pad"><ErrorMessage message={l.result.error.message} onRetry={l.result.reload} /></div>
  return (
    <Table loading={l.result.loading} caption={caption} data={l.rows} columns={columns} emptyIcon={icon}
           emptyTitle={l.filtered ? `No ${caption.toLowerCase()} match` : emptyTitle}
           emptyMessage={l.filtered ? 'Try another search, filter or date range.' : emptyMessage}
           pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }} />
  )
}

/** Unpaid invoices to choose from when no invoice was picked first. */
function useOpenInvoices(open, invoice) {
  return useApi(() => (open && !invoice ? salesApi.listInvoices({ status: 'issued', page_size: 100 }) : Promise.resolve(null)), [open, invoice?.id])
}

/** Money received from a customer against an invoice. */
export function ReceivePaymentModal({ open, invoice, options, onClose, onSave }) {
  const invoices = useOpenInvoices(open, invoice)
  if (!open) return null
  if (!invoice && !invoices.data)
    return (
      <Modal open onClose={onClose} title="Record Payment" size="sm">
        {invoices.error ? <ErrorMessage message={invoices.error.message} onRetry={invoices.reload} /> : <Loader label="Loading invoices…" />}
      </Modal>
    )
  const choices = invoice ? [invoice] : list(invoices.data?.results).filter((i) => Number(i.balance) > 0)
  if (choices.length === 0)
    return (
      <Modal open onClose={onClose} title="Record Payment" size="sm">
        <EmptyState compact title="No unpaid invoices" message="Payments are recorded against issued invoices with a balance." />
      </Modal>
    )
  const find = (id) => choices.find((i) => String(i.id) === String(id))
  return (
    <FormModal
      open
      onClose={onClose}
      title="Record Payment"
      subtitle="Receipt number is assigned automatically"
      submitLabel="Save Payment"
      initialValues={{ invoice_id: String(choices[0].id), amount: invoice ? invoice.balance : '', payment_date: todayISO() }}
      fields={[
        { name: 'invoice_id', label: 'Invoice', type: 'select', required: true, full: true,
          options: choices.map((i) => ({ value: String(i.id), label: `${i.invoice_number} · ${i.customer_name} · ${money(i.balance)} due` })) },
        { name: 'amount', label: 'Amount (₹)', type: 'number', required: true, min: 0.01,
          validate: (v, vals) => (find(vals.invoice_id) && Number(v) > Number(find(vals.invoice_id).balance) ? `Only ${money(find(vals.invoice_id).balance)} is outstanding` : undefined) },
        { name: 'payment_date', label: 'Payment date', type: 'date', required: true, validate: notFuture },
        { name: 'payment_method', label: 'Payment method', type: 'select', required: true, options: choiceOptions(options.data?.payment_methods) },
        { name: 'reference', label: 'Transaction reference', placeholder: 'UTR / cheque no.' },
        { name: 'notes', label: 'Notes', type: 'textarea' },
      ]}
      onSubmit={(v) => onSave({ ...v, reference: optionalText(v.reference), notes: optionalText(v.notes) })}
    />
  )
}

/** Goods a customer sends back against an invoice; credited when completed. */
export function SalesReturnModal({ open, invoice, options, onClose, onSave }) {
  const invoices = useOpenInvoices(open, invoice)
  const [picked, setPicked] = useState(null)
  const chosen = invoice ?? picked
  const detail = useApi(() => (open && chosen ? salesApi.getInvoice(chosen.id) : Promise.resolve(null)), [open, chosen?.id])
  if (!open) return null
  const close = () => {
    setPicked(null)
    onClose()
  }
  if (!chosen) {
    const choices = list(invoices.data?.results)
    return (
      <Modal open onClose={close} title="Record Sales Return" size="sm">
        {invoices.error ? <ErrorMessage message={invoices.error.message} onRetry={invoices.reload} />
          : !invoices.data ? <Loader label="Loading invoices…" />
          : choices.length === 0 ? <EmptyState compact title="No issued invoices" message="Returns are recorded against an invoice." />
          : (
            <div className="stack">
              <p className="muted">Choose the invoice the goods were sold on.</p>
              {choices.map((i) => (
                <Button key={i.id} variant="outline" onClick={() => setPicked(i)}>{i.invoice_number} · {i.customer_name}</Button>
              ))}
            </div>
          )}
      </Modal>
    )
  }
  if (!detail.data)
    return (
      <Modal open onClose={close} title="Record Sales Return" size="sm">
        {detail.error ? <ErrorMessage message={detail.error.message} onRetry={detail.reload} /> : <Loader label="Loading invoice…" />}
      </Modal>
    )
  const items = list(detail.data.items)
  return (
    <FormModal
      open
      onClose={close}
      title={`Sales Return · ${chosen.invoice_number}`}
      subtitle={`${chosen.customer_name}. The credit defaults to the invoiced price (after discount, with GST).`}
      submitLabel="Save Return"
      initialValues={{ product_id: String(items[0]?.product_id ?? ''), return_date: todayISO(), restock: 'yes' }}
      fields={[
        { name: 'product_id', label: 'Product', type: 'select', required: true, full: true,
          options: items.map((i) => ({ value: String(i.product_id), label: `${i.product} · ${i.quantity_kg} kg invoiced` })) },
        { name: 'quantity_kg', label: 'Quantity (kg)', type: 'number', required: true, min: 0.001 },
        { name: 'return_date', label: 'Return date', type: 'date', required: true, validate: notFuture },
        { name: 'reason', label: 'Reason', type: 'select', required: true, options: choiceOptions(options.data?.return_reasons) },
        { name: 'amount', label: 'Credit amount (₹)', type: 'number', min: 0, placeholder: 'Blank = at the invoiced price' },
        { name: 'restock', label: 'Goods', type: 'select', required: true,
          options: [{ value: 'yes', label: 'Put back into stock' }, { value: 'no', label: 'Not resellable (no stock change)' }] },
        { name: 'remarks', label: 'Remarks', type: 'textarea' },
      ]}
      onSubmit={async (v) => {
        await onSave({ ...v, invoice_id: chosen.id, amount: optionalNumber(v.amount), restock: v.restock === 'yes', remarks: optionalText(v.remarks) })
        setPicked(null)
      }}
    />
  )
}

export function SalesPaymentsPanel({ options, canReceive, refreshKey, onNew, onChanged }) {
  const toast = useToast()
  const [cancelling, setCancelling] = useState(null)
  const l = usePagedList(salesApi.listPayments, { payment_method: '', date_from: '', date_to: '' }, refreshKey)
  const cancel = async () => {
    await salesApi.cancelPayment(cancelling.id)
    toast.success(`${cancelling.receipt_number} cancelled`)
    onChanged()
  }
  return (
    <Card title="Payments Received" subtitle="Customer payments against invoices" bodyClassName="card__body--flush"
          action={canReceive && <Button size="sm" icon={Plus} onClick={onNew}>Record Payment</Button>}>
      <ListToolbar search={l.search} onSearch={l.setSearch} searchLabel="Search receipt, invoice, customer or reference" onFilter={l.setFilter}
                   filters={[{ name: 'payment_method', label: 'Filter by method', value: l.filters.payment_method, options: withAll('All methods', choiceOptions(options.data?.payment_methods)) }]}
                   dates={{ from: l.filters.date_from, to: l.filters.date_to, onChange: l.setFilter }} />
      <ListBody l={l} caption="Payments" icon={IndianRupee} emptyTitle="No payments received yet" emptyMessage="Payments recorded against invoices will be listed here."
        columns={[
          { key: 'receipt_number', header: 'Receipt', render: (r) => <strong className="nowrap">{r.receipt_number}</strong> },
          { key: 'payment_date', header: 'Date', render: (r) => <span className="nowrap">{date(r.payment_date)}</span> },
          { key: 'invoice_number', header: 'Invoice' },
          { key: 'customer', header: 'Customer' },
          { key: 'amount', header: 'Amount', align: 'right', render: (r) => money(r.amount) },
          { key: 'payment_method', header: 'Method' },
          { key: 'reference', header: 'Reference', render: (r) => dash(r.reference) },
          { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
          { key: 'actions', sticky: true, header: <span className="sr-only">Actions</span>, align: 'right',
            render: (r) => canReceive && r.can_cancel && <Button size="sm" variant="ghost" icon={XCircle} onClick={() => setCancelling(r)} aria-label={`Cancel ${r.receipt_number}`} /> },
        ]} />
      <ConfirmDialog open={Boolean(cancelling)} onClose={() => setCancelling(null)} onConfirm={cancel} danger title="Cancel payment?"
                     message={`${cancelling?.receipt_number ?? ''} (${money(cancelling?.amount)}) will no longer count towards ${cancelling?.invoice_number ?? 'the invoice'}.`}
                     confirmLabel="Cancel Payment" cancelLabel="Keep" />
    </Card>
  )
}

export function SalesReturnsPanel({ options, canManage, refreshKey, onNew, onChanged }) {
  const toast = useToast()
  const [confirm, setConfirm] = useState(null)
  const o = options.data ?? {}
  const l = usePagedList(salesApi.listReturns, { status: '', reason: '', date_from: '', date_to: '' }, refreshKey)
  const apply = async () => {
    await salesApi.setReturnStatus(confirm.row.id, confirm.status)
    toast.success(`${confirm.row.return_number} marked ${confirm.status}`)
    onChanged()
  }
  return (
    <Card title="Sales Returns" subtitle="Goods sent back by customers" bodyClassName="card__body--flush"
          action={canManage && <Button size="sm" icon={Plus} onClick={onNew}>Record Return</Button>}>
      <ListToolbar search={l.search} onSearch={l.setSearch} searchLabel="Search return, invoice, customer or product" onFilter={l.setFilter}
                   filters={[
                     { name: 'status', label: 'Filter by status', value: l.filters.status, options: withAll('All statuses', choiceOptions(o.return_statuses)) },
                     { name: 'reason', label: 'Filter by reason', value: l.filters.reason, options: withAll('All reasons', choiceOptions(o.return_reasons)) },
                   ]}
                   dates={{ from: l.filters.date_from, to: l.filters.date_to, onChange: l.setFilter }} />
      <ListBody l={l} caption="Sales returns" icon={Undo2} emptyTitle="No sales returns" emptyMessage="Goods returned by customers will be listed here."
        columns={[
          { key: 'return_number', header: 'Return', render: (r) => <strong className="nowrap">{r.return_number}</strong> },
          { key: 'return_date', header: 'Date', render: (r) => <span className="nowrap">{date(r.return_date)}</span> },
          { key: 'invoice_number', header: 'Invoice' },
          { key: 'customer', header: 'Customer' },
          { key: 'product', header: 'Product' },
          { key: 'quantity_kg', header: 'Quantity', align: 'right', render: (r) => `${r.quantity_kg} kg` },
          { key: 'reason', header: 'Reason' },
          { key: 'amount', header: 'Credit', align: 'right', render: (r) => money(r.amount) },
          { key: 'restock', header: 'Restocked', render: (r) => (r.restock ? 'Yes' : 'No') },
          { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
          { key: 'actions', sticky: true, header: <span className="sr-only">Actions</span>, align: 'right',
            render: (r) => canManage && r.can_update && (
              <span className="row-actions">
                <Button size="sm" variant="ghost" icon={CircleCheck} onClick={() => setConfirm({ row: r, status: 'completed' })} aria-label={`Mark ${r.return_number} completed`} />
                <Button size="sm" variant="ghost" icon={XCircle} onClick={() => setConfirm({ row: r, status: 'cancelled' })} aria-label={`Cancel ${r.return_number}`} />
              </span>
            ) },
        ]} />
      <ConfirmDialog open={Boolean(confirm)} onClose={() => setConfirm(null)} onConfirm={apply} danger={confirm?.status === 'cancelled'}
                     title={confirm?.status === 'completed' ? 'Complete return?' : 'Cancel return?'}
                     message={confirm?.status === 'completed'
                       ? `${money(confirm?.row.amount)} is credited against ${confirm?.row.invoice_number}.`
                       : confirm?.row.restock ? 'The restocked goods are taken out of stock again.' : 'The return is cancelled.'}
                     confirmLabel={confirm?.status === 'completed' ? 'Complete Return' : 'Cancel Return'} cancelLabel="Keep" />
    </Card>
  )
}
