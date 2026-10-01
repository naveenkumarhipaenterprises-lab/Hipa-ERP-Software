import { ArrowRightLeft, Download, Eye, FileCheck2, FileText, Pencil, Plus, Printer, ReceiptText, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { salesApi } from '../../../api/salesApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import PdfPreviewModal from '../../../components/common/PdfPreviewModal'
import Table from '../../../components/common/Table'
import TotalsSummary from '../../../components/common/TotalsSummary'
import { useApi } from '../../../hooks/useApi'
import { usePagedList } from '../../../hooks/usePagedList'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatRelativeTime } from '../../../utils/formatters'
import ListToolbar from '../../../components/common/ListToolbar'
import { choiceOptions, dash, date, list, money, withAll } from '../../../utils/display'
import DocumentEditor from './DocumentEditor'
import { ITEM_COLUMNS } from './documentColumns'

/** Sales quotations: list, create / edit, status changes, PDF preview / print / download and conversions. */
export default function QuotationsPanel({ options, canManage, refreshKey, onChanged }) {
  const toast = useToast()
  const o = options.data ?? {}
  const [editing, setEditing] = useState(null) // detail | {} for new
  const [viewing, setViewing] = useState(null)
  const l = usePagedList(salesApi.listQuotations, { status: '', date_from: '', date_to: '' }, refreshKey)

  const save = async (body) => {
    const q = editing.id ? await salesApi.updateQuotation(editing.id, body) : await salesApi.createQuotation(body)
    toast.success(editing.id ? `${q.quotation_number} updated` : `Quotation ${q.quotation_number} saved`)
    onChanged()
    if (!editing.id) setViewing(q)
  }

  const columns = [
    { key: 'quotation_number', header: 'Quotation No.', render: (r) => <strong className="nowrap">{r.quotation_number}</strong> },
    { key: 'quotation_date', header: 'Date', render: (r) => <span className="nowrap">{date(r.quotation_date)}</span> },
    { key: 'valid_until', header: 'Valid Until', render: (r) => <span className="nowrap">{date(r.valid_until)}</span> },
    { key: 'customer_name', header: 'Customer', render: (r) => <>{r.customer_name}{r.company_name ? <span className="muted"> · {r.company_name}</span> : null}</> },
    { key: 'products', header: 'Products', render: (r) => dash(r.products) },
    { key: 'grand_total', header: 'Grand Total', align: 'right', render: (r) => money(r.grand_total) },
    { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
    { key: 'converted', header: 'Converted To', render: (r) => [r.sales_order_number, r.invoice_number].filter(Boolean).join(', ') || '—' },
    { key: 'actions', sticky: true, header: <span className="sr-only">Actions</span>, align: 'right',
      render: (r) => <Button size="sm" variant="ghost" icon={Eye} onClick={() => setViewing(r)} aria-label={`Open ${r.quotation_number}`} /> },
  ]

  return (
    <Card title="Quotations" subtitle="Prices offered before the customer confirms the sale" bodyClassName="card__body--flush"
          action={canManage && <Button size="sm" icon={Plus} onClick={() => setEditing({})}>New Quotation</Button>}>
      <ListToolbar search={l.search} onSearch={l.setSearch} searchLabel="Search quotation no., customer or product" onFilter={l.setFilter}
                   filters={[{ name: 'status', label: 'Filter by status', value: l.filters.status, options: withAll('All statuses', choiceOptions(o.quotation_statuses)) }]}
                   dates={{ from: l.filters.date_from, to: l.filters.date_to, onChange: l.setFilter }} />
      {l.result.error && !l.result.loading ? (
        <div className="card__pad"><ErrorMessage message={l.result.error.message} onRetry={l.result.reload} /></div>
      ) : (
        <Table loading={l.result.loading} caption="Quotations" data={l.rows} columns={columns} emptyIcon={FileText}
               emptyTitle={l.filtered ? 'No quotations match' : 'No quotations yet'}
               emptyMessage={l.filtered ? 'Try another search, status or date range.' : 'Create a quotation to send prices to a customer.'}
               pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }} />
      )}

      <DocumentEditor open={Boolean(editing)} kind="quotation" document={editing?.id ? editing : null} options={options}
                      onClose={() => setEditing(null)} onSave={save} />
      <QuotationDetail quotation={viewing} canManage={canManage} statuses={o.quotation_statuses} refreshKey={refreshKey}
                       onClose={() => setViewing(null)} onEdit={(q) => { setViewing(null); setEditing(q) }} onChanged={onChanged} />
    </Card>
  )
}

function QuotationDetail({ quotation, canManage, statuses, refreshKey, onClose, onEdit, onChanged }) {
  const toast = useToast()
  const [tick, setTick] = useState(0)
  const [pdf, setPdf] = useState(null) // { print: bool }
  const [statusOpen, setStatusOpen] = useState(false)
  const [confirm, setConfirm] = useState(null) // 'order' | 'invoice' | 'delete'
  const detail = useApi(() => (quotation ? salesApi.getQuotation(quotation.id) : Promise.resolve(null)), [quotation?.id, refreshKey, tick])
  if (!quotation) return null
  const q = detail.data
  const changed = () => {
    setTick((t) => t + 1)
    onChanged()
  }

  const run = async () => {
    if (confirm === 'order') {
      const res = await salesApi.quotationToOrder(q.id)
      toast.success(`Sales order ${res.sales_order.order_number} created from ${q.quotation_number}`)
    } else if (confirm === 'invoice') {
      const res = await salesApi.quotationToInvoice(q.id)
      toast.success(`Sales invoice ${res.invoice.invoice_number} created from ${q.quotation_number}`)
    } else {
      await salesApi.deleteQuotation(q.id)
      toast.success(`${q.quotation_number} deleted`)
      onChanged()
      onClose()
      return
    }
    changed()
  }

  const nextStatuses = list(q?.next_statuses)
  const statusOptions = choiceOptions(statuses).filter((s) => nextStatuses.includes(s.label))

  return (
    <>
      <Modal open onClose={onClose} size="lg" title={quotation.quotation_number}
             subtitle={q ? `${q.customer_name} · ${formatDate(q.quotation_date)} · valid until ${formatDate(q.valid_until)}` : ''}>
        {detail.error && !detail.loading ? (
          <ErrorMessage message={detail.error.message} onRetry={detail.reload} />
        ) : !q ? (
          <Loader label="Loading quotation…" />
        ) : (
          <div className="stack">
            <div className="doc-actions">
              <Button size="sm" variant="outline" icon={Eye} onClick={() => setPdf({ print: false })}>Preview</Button>
              <Button size="sm" variant="outline" icon={Printer} onClick={() => setPdf({ print: true })}>Print</Button>
              <Button size="sm" variant="outline" icon={Download} onClick={() => salesApi.downloadQuotationPdf(q.id).catch((e) => toast.error(e.message))}>Download PDF</Button>
              {canManage && q.can_edit && <Button size="sm" variant="outline" icon={Pencil} onClick={() => onEdit(q)}>Edit</Button>}
              {canManage && statusOptions.length > 0 && <Button size="sm" variant="outline" icon={ArrowRightLeft} onClick={() => setStatusOpen(true)}>Change Status</Button>}
              {canManage && q.can_convert_to_order && <Button size="sm" icon={FileCheck2} onClick={() => setConfirm('order')}>Convert to Sales Order</Button>}
              {canManage && q.can_convert_to_invoice && <Button size="sm" icon={ReceiptText} onClick={() => setConfirm('invoice')}>Convert to Sales Invoice</Button>}
              {canManage && q.can_delete && <Button size="sm" variant="ghost" icon={Trash2} onClick={() => setConfirm('delete')}>Delete</Button>}
            </div>
            {canManage && !q.customer_id && ['Draft', 'Sent', 'Accepted'].includes(q.status) && (
              <p className="muted">Link this quotation to a customer (Edit → Existing customer) before converting it.</p>
            )}
            <dl className="detail-grid">
              {[['Status', <Badge key="s">{q.status}</Badge>], ['Customer', q.customer_name], ['Company', q.company_name], ['Phone', q.phone], ['Email', q.email],
                ['GSTIN', q.gstin], ['Billing address', q.billing_address], ['Shipping address', q.shipping_address || q.billing_address],
                ['Sales order', q.sales_order_number], ['Invoice', q.invoice_number]].map(([k, v]) => (
                <div key={k}><dt>{k}</dt><dd>{v || '—'}</dd></div>
              ))}
            </dl>
            <Table compact caption="Quotation products" data={list(q.items)} columns={ITEM_COLUMNS} />
            <TotalsSummary totals={{ subtotal: q.subtotal, discount: q.discount_amount, gst: q.gst_amount, total: q.grand_total }} totalLabel="Grand Total" />
            <dl className="detail-grid">
              {[['Payment terms', q.payment_terms], ['Delivery terms', q.delivery_terms], ['Notes', q.notes], ['Terms & conditions', q.terms_conditions]].map(([k, v]) => (
                <div key={k}><dt>{k}</dt><dd style={{ whiteSpace: 'pre-line' }}>{v || '—'}</dd></div>
              ))}
            </dl>
            <h3 className="card__title">Status history</h3>
            <Table compact caption="Status history" data={list(q.status_history)} rowKey={(r, i) => i}
                   columns={[{ key: 'to', header: 'Status', render: (r) => <Badge>{r.to}</Badge> },
                             { key: 'from', header: 'From', render: (r) => dash(r.from) },
                             { key: 'changed_by', header: 'By', render: (r) => dash(r.changed_by) },
                             { key: 'changed_at', header: 'When', render: (r) => formatRelativeTime(r.changed_at) },
                             { key: 'note', header: 'Note', render: (r) => dash(r.note) }]} />
          </div>
        )}
      </Modal>

      <PdfPreviewModal open={Boolean(pdf)} autoPrint={pdf?.print} title={`Quotation ${quotation.quotation_number}`}
                       load={() => salesApi.quotationPdf(quotation.id)} onDownload={() => salesApi.downloadQuotationPdf(quotation.id)}
                       onClose={() => setPdf(null)} />
      <FormModal open={statusOpen} onClose={() => setStatusOpen(false)} title="Change Status" subtitle={q?.quotation_number}
                 submitLabel="Update Status" initialValues={{ status: statusOptions[0]?.value ?? '' }}
                 fields={[{ name: 'status', label: 'New status', type: 'select', required: true, options: statusOptions },
                          { name: 'note', label: 'Note', type: 'textarea', placeholder: 'e.g. Customer confirmed by phone' }]}
                 onSubmit={async (v) => {
                   const res = await salesApi.setQuotationStatus(q.id, v.status, v.note?.trim() || undefined)
                   toast.success(`${res.quotation_number} is now ${res.status}`)
                   changed()
                 }} />
      <ConfirmDialog
        open={Boolean(confirm)}
        onClose={() => setConfirm(null)}
        onConfirm={run}
        danger={confirm === 'delete'}
        title={{ order: 'Convert to sales order?', invoice: 'Convert to sales invoice?', delete: 'Delete quotation?' }[confirm] ?? ''}
        message={{
          order: 'A new sales order is created with the same customer, products, prices, discounts and GST. Stock is reserved (taken out) now. The quotation becomes Converted.',
          invoice: q?.sales_order_number
            ? `The sales order ${q.sales_order_number} is invoiced. Its stock has already gone out, so stock does not change again.`
            : 'A new sales invoice is created with its own number and the same customer and products. Stock goes out now. The quotation becomes Converted.',
          delete: 'This draft quotation will be deleted.',
        }[confirm]}
        confirmLabel={{ order: 'Create Sales Order', invoice: 'Create Sales Invoice', delete: 'Delete' }[confirm]}
        cancelLabel="Back"
      />
    </>
  )
}
