import { HandCoins, XCircle } from 'lucide-react'
import { useState } from 'react'
import { salesApi } from '../../../api/salesApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import ListToolbar from '../../../components/common/ListToolbar'
import Table from '../../../components/common/Table'
import { usePagedList } from '../../../hooks/usePagedList'
import { useRequestKey } from '../../../hooks/useRequestKey'
import { useToast } from '../../../hooks/useToast'
import { choiceOptions, dash, date, money, optionalText, withAll } from '../../../utils/display'
import { todayISO } from '../../../utils/formatters'

const KINDS = [{ value: 'refund', label: 'Refund (pay the money back)' }, { value: 'credit', label: 'Keep as customer credit' }]
const isRefund = (v) => v.kind === 'refund'

/**
 * An invoice's overpayment (e.g. goods returned after paying): decide each time whether it is paid back (refund)
 * or kept as the customer's credit for a later payment ("Customer credit" payment method). Part of it is fine.
 */
export function SettleOverpaymentModal({ open, invoice, options, onClose, onSave }) {
  const requestKey = useRequestKey(open) // one settlement per opening, even if sent twice
  if (!open || !invoice) return null
  const methods = choiceOptions(options.data?.payment_methods).filter((m) => m.value !== 'Customer credit')
  return (
    <FormModal
      open
      onClose={onClose}
      title="Settle Overpayment"
      subtitle={`${invoice.invoice_number} · ${invoice.customer_name} · ${money(invoice.overpaid)} overpaid`}
      submitLabel="Save"
      initialValues={{ kind: 'refund', amount: invoice.overpaid, date: todayISO() }}
      fields={[
        { name: 'kind', label: 'What happens to it', type: 'select', required: true, full: true, options: KINDS },
        { name: 'amount', label: 'Amount (₹)', type: 'number', required: true, min: 0.01,
          validate: (v) => (Number(v) > Number(invoice.overpaid) ? `Only ${money(invoice.overpaid)} was overpaid` : undefined) },
        { name: 'date', label: 'Date', type: 'date', required: true, validate: (v) => (v > todayISO() ? "Can't be in the future" : undefined) },
        { name: 'payment_method', label: 'Refunded by', type: 'select', required: true, options: methods, visible: isRefund },
        { name: 'reference', label: 'Transaction reference', placeholder: 'UTR / cheque no.', visible: isRefund },
        { name: 'notes', label: 'Notes', type: 'textarea' },
      ]}
      onSubmit={(v) => onSave({ ...v, invoice_id: invoice.id, reference: optionalText(v.reference), notes: optionalText(v.notes),
                                request_key: requestKey })}
    />
  )
}

/** Refunds paid out and credits kept, with cancel (a credit already used can't be cancelled; the server says so). */
export function SalesSettlementsPanel({ canReceive, refreshKey, onChanged }) {
  const toast = useToast()
  const [cancelling, setCancelling] = useState(null)
  const l = usePagedList(salesApi.listSettlements, { kind: '' }, refreshKey)
  const cancel = async () => {
    await salesApi.cancelSettlement(cancelling.id)
    toast.success(`${cancelling.number} cancelled`)
    onChanged()
  }
  return (
    <Card title="Refunds & Credits" subtitle="Overpayments paid back, or kept as customer credit" bodyClassName="card__body--flush">
      <ListToolbar search={l.search} onSearch={l.setSearch} searchLabel="Search number, invoice, customer or reference" onFilter={l.setFilter}
                   filters={[{ name: 'kind', label: 'Filter by type', value: l.filters.kind,
                               options: withAll('Refunds and credits', [{ value: 'refund', label: 'Refunds' }, { value: 'credit', label: 'Customer credit' }]) }]} />
      {l.result.error && !l.result.loading ? (
        <div className="card__pad"><ErrorMessage message={l.result.error.message} onRetry={l.result.reload} /></div>
      ) : (
        <Table loading={l.result.loading} caption="Refunds and credits" data={l.rows} emptyIcon={HandCoins}
               emptyTitle={l.filtered ? 'No refunds or credits match' : 'No refunds or credits yet'}
               emptyMessage={l.filtered ? 'Try another search or type.' : 'When a customer has paid more than they owe, settle it from the invoice.'}
               pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }}
               columns={[
                 { key: 'number', header: 'Number', render: (r) => <strong className="nowrap">{r.number}</strong> },
                 { key: 'date', header: 'Date', render: (r) => <span className="nowrap">{date(r.date)}</span> },
                 { key: 'kind', header: 'Type' },
                 { key: 'invoice_number', header: 'Invoice' },
                 { key: 'customer', header: 'Customer' },
                 { key: 'amount', header: 'Amount', align: 'right', render: (r) => money(r.amount) },
                 { key: 'payment_method', header: 'Refunded by', render: (r) => dash(r.payment_method) },
                 { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
                 { key: 'actions', sticky: true, align: 'right', header: <span className="sr-only">Actions</span>,
                   render: (r) => canReceive && r.can_cancel && (
                     <Button size="sm" variant="ghost" icon={XCircle} onClick={() => setCancelling(r)} aria-label={`Cancel ${r.number}`} />
                   ) },
               ]} />
      )}
      <ConfirmDialog open={Boolean(cancelling)} onClose={() => setCancelling(null)} onConfirm={cancel} danger
                     title={`Cancel ${cancelling?.number ?? ''}?`}
                     message={`${cancelling?.invoice_number ?? 'The invoice'} will show ${money(cancelling?.amount)} overpaid again.`}
                     confirmLabel="Cancel It" cancelLabel="Keep" />
    </Card>
  )
}
