import { Ban, Download, Eye, IndianRupee, Pencil, Plus, Printer, ReceiptText, Undo2 } from 'lucide-react'
import { useState } from 'react'
import { salesApi } from '../../../api/salesApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import ListToolbar from '../../../components/common/ListToolbar'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import PdfPreviewModal from '../../../components/common/PdfPreviewModal'
import Table from '../../../components/common/Table'
import TotalsSummary from '../../../components/common/TotalsSummary'
import { useApi } from '../../../hooks/useApi'
import { usePagedList } from '../../../hooks/usePagedList'
import { useToast } from '../../../hooks/useToast'
import { choiceOptions, dash, date, idOptions, list, money, withAll } from '../../../utils/display'
import { formatDate } from '../../../utils/formatters'
import DocumentEditor from './DocumentEditor'
import { ITEM_COLUMNS } from './documentColumns'

/** Sales invoices: list, create (direct), edit, cancel, PDF preview / print / download, payments and returns. */
export default function InvoicesPanel({ options, canManage, canReceive, refreshKey, onChanged, onPay, onReturn }) {
  const toast = useToast()
  const o = options.data ?? {}
  const [editing, setEditing] = useState(null)
  const [viewing, setViewing] = useState(null)
  const l = usePagedList(salesApi.listInvoices, { status: '', payment_status: '', customer: '', date_from: '', date_to: '' }, refreshKey)

  const save = async (body) => {
    const inv = editing.id ? await salesApi.updateInvoice(editing.id, body) : await salesApi.createInvoice(body)
    toast.success(editing.id ? `${inv.invoice_number} updated` : `Invoice ${inv.invoice_number} saved`)
    onChanged()
    if (!editing.id) setViewing(inv)
  }

  const columns = [
    { key: 'invoice_number', header: 'Invoice No.', render: (r) => <strong className="nowrap">{r.invoice_number}</strong> },
    { key: 'invoice_date', header: 'Date', render: (r) => <span className="nowrap">{date(r.invoice_date)}</span> },
    { key: 'due_date', header: 'Due', render: (r) => <span className="nowrap">{date(r.due_date)}</span> },
    { key: 'customer_name', header: 'Customer' },
    { key: 'products', header: 'Products', render: (r) => dash(r.products) },
    { key: 'grand_total', header: 'Total', align: 'right', render: (r) => money(r.grand_total) },
    { key: 'balance', header: 'Balance', align: 'right', render: (r) => (r.status === 'Cancelled' ? '—' : money(r.balance)) },
    { key: 'payment_status', header: 'Payment', render: (r) => (r.payment_status ? <Badge>{r.payment_status}</Badge> : <Badge>{r.status}</Badge>) },
    { key: 'source', header: 'From', render: (r) => r.sales_order_number || r.quotation_number || 'Direct' },
    { key: 'actions', sticky: true, header: <span className="sr-only">Actions</span>, align: 'right',
      render: (r) => (
        <span className="row-actions">
          <Button size="sm" variant="ghost" icon={Eye} onClick={() => setViewing(r)} aria-label={`Open ${r.invoice_number}`} />
          {canReceive && r.can_record_payment && <Button size="sm" variant="ghost" icon={IndianRupee} onClick={() => onPay(r)} aria-label={`Record payment for ${r.invoice_number}`} />}
        </span>
      ) },
  ]

  return (
    <Card title="Sales Invoices" subtitle="Invoices raised to customers" bodyClassName="card__body--flush"
          action={canManage && <Button size="sm" icon={Plus} onClick={() => setEditing({})}>New Invoice</Button>}>
      <ListToolbar search={l.search} onSearch={l.setSearch} searchLabel="Search invoice no., customer or product" onFilter={l.setFilter}
                   filters={[
                     { name: 'payment_status', label: 'Filter by payment', value: l.filters.payment_status, options: withAll('All payments', choiceOptions(o.invoice_payment_statuses)) },
                     { name: 'status', label: 'Filter by status', value: l.filters.status, options: withAll('Issued and cancelled', choiceOptions(o.invoice_statuses)) },
                     { name: 'customer', label: 'Filter by customer', value: l.filters.customer, options: withAll('All customers', idOptions(o.customers)) },
                   ]}
                   dates={{ from: l.filters.date_from, to: l.filters.date_to, onChange: l.setFilter }} />
      {l.result.error && !l.result.loading ? (
        <div className="card__pad"><ErrorMessage message={l.result.error.message} onRetry={l.result.reload} /></div>
      ) : (
        <Table loading={l.result.loading} caption="Sales invoices" data={l.rows} columns={columns} emptyIcon={ReceiptText}
               emptyTitle={l.filtered ? 'No invoices match' : 'No sales invoices yet'}
               emptyMessage={l.filtered ? 'Try another search, filter or date range.' : 'Create an invoice, or convert a quotation or sales order.'}
               pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }} />
      )}

      <DocumentEditor open={Boolean(editing)} kind="invoice" document={editing?.id ? editing : null} options={options}
                      onClose={() => setEditing(null)} onSave={save} />
      <InvoiceDetail invoice={viewing} canManage={canManage} canReceive={canReceive} refreshKey={refreshKey} onClose={() => setViewing(null)}
                     onEdit={(inv) => { setViewing(null); setEditing(inv) }} onChanged={onChanged}
                     onPay={(inv) => { setViewing(null); onPay(inv) }} onReturn={(inv) => { setViewing(null); onReturn(inv) }} />
    </Card>
  )
}

export function InvoiceDetail({ invoice, canManage, canReceive, refreshKey, onClose, onEdit, onChanged, onPay, onReturn }) {
  const toast = useToast()
  const [tick, setTick] = useState(0)
  const [pdf, setPdf] = useState(null)
  const [cancelling, setCancelling] = useState(false)
  const detail = useApi(() => (invoice ? salesApi.getInvoice(invoice.id) : Promise.resolve(null)), [invoice?.id, refreshKey, tick])
  if (!invoice) return null
  const inv = detail.data

  const cancel = async () => {
    await salesApi.cancelInvoice(inv.id)
    toast.success(`${inv.invoice_number} cancelled`)
    setTick((t) => t + 1)
    onChanged()
  }

  return (
    <>
      <Modal open onClose={onClose} size="lg" title={invoice.invoice_number}
             subtitle={inv ? `${inv.customer_name} · ${formatDate(inv.invoice_date)}${inv.due_date ? ` · due ${formatDate(inv.due_date)}` : ''}` : ''}>
        {detail.error && !detail.loading ? (
          <ErrorMessage message={detail.error.message} onRetry={detail.reload} />
        ) : !inv ? (
          <Loader label="Loading invoice…" />
        ) : (
          <div className="stack">
            <div className="doc-actions">
              <Button size="sm" variant="outline" icon={Eye} onClick={() => setPdf({ print: false })}>Preview</Button>
              <Button size="sm" variant="outline" icon={Printer} onClick={() => setPdf({ print: true })}>Print Invoice</Button>
              <Button size="sm" variant="outline" icon={Download} onClick={() => salesApi.downloadInvoicePdf(inv.id).catch((e) => toast.error(e.message))}>Download PDF</Button>
              {canManage && inv.can_edit && <Button size="sm" variant="outline" icon={Pencil} onClick={() => onEdit(inv)}>Edit</Button>}
              {canReceive && inv.can_record_payment && <Button size="sm" icon={IndianRupee} onClick={() => onPay(inv)}>Record Payment</Button>}
              {canManage && inv.status === 'Issued' && <Button size="sm" variant="outline" icon={Undo2} onClick={() => onReturn(inv)}>Record Return</Button>}
              {canManage && inv.can_cancel && <Button size="sm" variant="ghost" icon={Ban} onClick={() => setCancelling(true)}>Cancel Invoice</Button>}
            </div>
            <dl className="detail-grid">
              {[['Status', <Badge key="s">{inv.status}</Badge>], ['Payment', inv.payment_status ? <Badge key="p">{inv.payment_status}</Badge> : '—'],
                ['Customer', inv.customer_name], ['Company', inv.company_name], ['GSTIN', inv.gstin], ['Phone', inv.phone], ['Email', inv.email],
                ['Billing address', inv.billing_address], ['Shipping address', inv.shipping_address || inv.billing_address],
                ['Sales order', inv.sales_order_number], ['Quotation', inv.quotation_number]].map(([k, v]) => (
                <div key={k}><dt>{k}</dt><dd>{v || '—'}</dd></div>
              ))}
            </dl>
            <Table compact caption="Invoice products" data={list(inv.items)} columns={ITEM_COLUMNS} />
            <TotalsSummary totals={{ subtotal: inv.subtotal, discount: inv.discount_amount, gst: inv.gst_amount, total: inv.grand_total }}
                           totalLabel="Invoice Total" />
            <dl className="detail-grid">
              {[['Paid', money(inv.amount_paid)], ['Credited (returns)', money(inv.credited_amount)], ['Balance due', money(inv.balance)],
                ['Payment terms', inv.payment_terms || '—'], ['Notes', inv.notes || '—']].map(([k, v]) => (
                <div key={k}><dt>{k}</dt><dd style={{ whiteSpace: 'pre-line' }}>{v}</dd></div>
              ))}
            </dl>
            <h3 className="card__title">Payments</h3>
            <Table compact caption="Payments received" data={list(inv.payments)} emptyTitle="No payments yet" emptyMessage="Payments received will be listed here."
                   columns={[{ key: 'receipt_number', header: 'Receipt' }, { key: 'payment_date', header: 'Date', render: (r) => date(r.payment_date) },
                             { key: 'amount', header: 'Amount', align: 'right', render: (r) => money(r.amount) }, { key: 'payment_method', header: 'Method' },
                             { key: 'reference', header: 'Reference', render: (r) => dash(r.reference) }, { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> }]} />
            {list(inv.returns).length > 0 && (
              <>
                <h3 className="card__title">Returns</h3>
                <Table compact caption="Returns" data={inv.returns}
                       columns={[{ key: 'return_number', header: 'Return' }, { key: 'product', header: 'Product' },
                                 { key: 'quantity_kg', header: 'Quantity', align: 'right', render: (r) => `${r.quantity_kg} kg` },
                                 { key: 'amount', header: 'Credit', align: 'right', render: (r) => money(r.amount) }, { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> }]} />
              </>
            )}
          </div>
        )}
      </Modal>
      <PdfPreviewModal open={Boolean(pdf)} autoPrint={pdf?.print} title={`Invoice ${invoice.invoice_number}`}
                       load={() => salesApi.invoicePdf(invoice.id)} onDownload={() => salesApi.downloadInvoicePdf(invoice.id)} onClose={() => setPdf(null)} />
      <ConfirmDialog open={cancelling} onClose={() => setCancelling(false)} onConfirm={cancel} danger title="Cancel invoice?"
                     message={inv?.sales_order_number
                       ? 'The invoice is cancelled. Stock stays with its sales order.'
                       : 'The invoice is cancelled and its products go back into stock. Payments and returns must be cancelled first.'}
                     confirmLabel="Cancel Invoice" cancelLabel="Keep" />
    </>
  )
}
