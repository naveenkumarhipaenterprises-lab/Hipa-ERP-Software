import Badge from '../../../components/common/Badge'
import { formatDate, formatINR } from '../../../utils/formatters'

const TYPE_LABEL = { income: 'Income', expense: 'Expense' }

/** Transaction table columns; `onView(row)` makes the description open the details. */
export function transactionColumns(onView) {
  return [
    { key: 'date', header: 'Date', render: (r) => <span className="nowrap">{r.date ? formatDate(r.date) : '—'}</span> },
    {
      key: 'description',
      header: 'Description',
      render: (r) =>
        onView ? (
          <button type="button" className="link link--strong table-link cell-clip" onClick={() => onView(r)}>
            {r.description || '—'}
          </button>
        ) : (
          r.description || '—'
        ),
    },
    { key: 'type', header: 'Type', render: (r) => (r.type ? <Badge tone={r.type === 'income' ? 'green' : 'red'}>{TYPE_LABEL[r.type] ?? r.type}</Badge> : '—') },
    {
      key: 'amount',
      header: 'Amount',
      align: 'right',
      render: (r) =>
        r.amount == null ? '—' : <span className={r.type === 'income' ? 'text-up' : r.type === 'expense' ? 'text-down' : ''}>{formatINR(r.amount)}</span>,
    },
    { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
  ]
}
