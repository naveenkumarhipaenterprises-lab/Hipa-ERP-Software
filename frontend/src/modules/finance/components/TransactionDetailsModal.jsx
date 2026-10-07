import { CircleCheck, Pencil } from 'lucide-react'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import { formatDate, formatINR } from '../../../utils/formatters'

const TYPE_LABEL = { income: 'Income', expense: 'Expense' }

/** One transaction; managers can edit it, or mark a pending one paid. */
export default function TransactionDetailsModal({ transaction: t, onClose, onEdit, onMarkPaid }) {
  if (!t) return null
  const footer = (onEdit || (onMarkPaid && t.can_mark_paid)) && (
    <>
      {onEdit && <Button variant="outline" icon={Pencil} onClick={() => onEdit(t)}>Edit</Button>}
      {onMarkPaid && t.can_mark_paid && (
        <Button icon={CircleCheck} onClick={() => onMarkPaid(t)}>{t.type === 'income' ? 'Mark received' : 'Mark paid'}</Button>
      )}
    </>
  )
  return (
    <Modal open onClose={onClose} title={t.description || 'Transaction'} subtitle={t.date ? formatDate(t.date) : undefined} footer={footer || undefined}>
      <dl className="detail-list">
        <dt>Type</dt>
        <dd>{t.type ? <Badge tone={t.type === 'income' ? 'green' : 'red'}>{TYPE_LABEL[t.type] ?? t.type}</Badge> : '—'}</dd>
        <dt>Amount</dt>
        <dd>{t.amount != null ? formatINR(t.amount) : '—'}</dd>
        <dt>Category</dt>
        <dd>{t.category || '—'}</dd>
        {t.party && (
          <>
            <dt>Pay to</dt>
            <dd>{t.party}</dd>
          </>
        )}
        {t.due_date && (
          <>
            <dt>Due date</dt>
            <dd>{formatDate(t.due_date)}</dd>
          </>
        )}
        <dt>Reference</dt>
        <dd>{t.reference || '—'}</dd>
        <dt>Status</dt>
        <dd>{t.status ? <Badge>{t.status}</Badge> : '—'}</dd>
      </dl>
    </Modal>
  )
}
