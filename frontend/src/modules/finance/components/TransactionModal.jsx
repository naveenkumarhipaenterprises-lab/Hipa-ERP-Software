import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])
const PAY_STATUS = [
  { value: 'completed', label: 'Paid now' },
  { value: 'pending', label: 'To be paid (pending payment)' },
]
const pending = (v) => v.status === 'pending'

/**
 * Records income or expense (POST /finance/transactions/), or edits one (PATCH /finance/transactions/<id>/)
 * when `transaction` is given. Categories come from GET /finance/options/. An expense can be recorded as
 * a pending payment with the payee and due date; it is settled later with "Mark paid".
 */
export default function TransactionModal({ type, transaction, options, onClose, onSave }) {
  const kind = transaction?.type ?? type
  if (!kind) return null
  const editing = Boolean(transaction)
  const noun = kind === 'income' ? 'Income' : 'Expense'
  const title = editing ? `Edit ${noun}` : `Record ${noun}`
  return (
    <OptionsGate options={options} title={title} onClose={onClose}>
      {(data) => {
        const categories = list(kind === 'income' ? data.income_categories : data.expense_categories)
        if (categories.length === 0) {
          return (
            <Modal open onClose={onClose} title={title} size="sm">
              <EmptyState compact title={`No ${kind} categories set up`} message="Contact your administrator to add categories." />
            </Modal>
          )
        }
        // Payee and due date: for a new expense when it is still to be paid, or when editing a pending one
        const showPayee = editing ? () => transaction.can_mark_paid === true : (v) => kind === 'expense' && pending(v)
        return (
          <FormModal
            open
            onClose={onClose}
            title={title}
            subtitle={editing ? transaction.description : kind === 'income' ? 'Money received' : 'Money paid out or to pay'}
            submitLabel={editing ? 'Save Changes' : `Save ${noun}`}
            initialValues={
              editing
                ? {
                    description: transaction.description, category: transaction.category_value, amount: transaction.amount,
                    date: transaction.date, reference: transaction.reference ?? '', party: transaction.party ?? '',
                    due_date: transaction.due_date ?? '',
                  }
                : { date: todayISO(), status: 'completed' }
            }
            fields={[
              { name: 'description', label: 'Description', required: true, full: true, placeholder: 'What is this transaction for?' },
              { name: 'category', label: 'Category', type: 'select', required: true, options: categories, placeholder: 'Select category' },
              { name: 'amount', label: 'Amount (₹)', type: 'number', required: true, min: 0.01, placeholder: 'Amount in rupees' },
              {
                name: 'date',
                label: 'Date',
                type: 'date',
                required: true,
                validate: (v) => (v > todayISO() ? 'Date cannot be in the future' : undefined),
              },
              { name: 'reference', label: 'Invoice / reference no.', placeholder: 'Optional' },
              ...(!editing && kind === 'expense' ? [{ name: 'status', label: 'Payment', type: 'select', required: true, options: PAY_STATUS }] : []),
              { name: 'party', label: 'Pay to', placeholder: 'Supplier, utility or person', visible: showPayee },
              { name: 'due_date', label: 'Due date', type: 'date', visible: showPayee },
            ]}
            onSubmit={(values) =>
              onSave({
                ...values,
                ...(editing ? {} : { type: kind }),
                description: values.description.trim(),
                reference: values.reference?.trim() ?? '',
                ...(values.party !== undefined ? { party: values.party.trim() } : {}),
              })
            }
          />
        )
      }}
    </OptionsGate>
  )
}
