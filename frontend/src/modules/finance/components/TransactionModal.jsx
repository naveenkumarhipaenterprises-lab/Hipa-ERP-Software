import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])

/** Records income or expense (POST /finance/transactions/). Categories come from GET /finance/options/. */
export default function TransactionModal({ type, options, onClose, onSave }) {
  if (!type) return null
  const title = type === 'income' ? 'Record Income' : 'Record Expense'
  return (
    <OptionsGate options={options} title={title} onClose={onClose}>
      {(data) => {
        const categories = list(type === 'income' ? data.income_categories : data.expense_categories)
        if (categories.length === 0) {
          return (
            <Modal open onClose={onClose} title={title} size="sm">
              <EmptyState compact title={`No ${type} categories set up`} message="Contact your administrator to add categories." />
            </Modal>
          )
        }
        return (
          <FormModal
            open
            onClose={onClose}
            title={title}
            subtitle={type === 'income' ? 'Money received' : 'Money paid out'}
            submitLabel={type === 'income' ? 'Save Income' : 'Save Expense'}
            initialValues={{ date: todayISO() }}
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
            ]}
            onSubmit={(values) =>
              onSave({ ...values, type, description: values.description.trim(), reference: values.reference?.trim() || undefined })
            }
          />
        )
      }}
    </OptionsGate>
  )
}
