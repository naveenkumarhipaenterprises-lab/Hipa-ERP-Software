import Badge from '../../../components/common/Badge'
import Modal from '../../../components/common/Modal'
import { formatDate, formatINR } from '../../../utils/formatters'

const TYPE_LABEL = { income: 'Income', expense: 'Expense' }

/** Read-only view of one transaction. */
export default function TransactionDetailsModal({ transaction: t, onClose }) {
  if (!t) return null
  return (
    <Modal open onClose={onClose} title={t.description || 'Transaction'} subtitle={t.date ? formatDate(t.date) : undefined}>
      <dl className="detail-list">
        <dt>Type</dt>
        <dd>{t.type ? <Badge tone={t.type === 'income' ? 'green' : 'red'}>{TYPE_LABEL[t.type] ?? t.type}</Badge> : '—'}</dd>
        <dt>Amount</dt>
        <dd>{t.amount != null ? formatINR(t.amount) : '—'}</dd>
        <dt>Category</dt>
        <dd>{t.category || '—'}</dd>
        <dt>Reference</dt>
        <dd>{t.reference || '—'}</dd>
        <dt>Status</dt>
        <dd>{t.status ? <Badge>{t.status}</Badge> : '—'}</dd>
      </dl>
    </Modal>
  )
}
