import FormModal from '../../../components/common/FormModal'

/** Sets the current period's targets (PUT /finance/budget/), pre-filled with the saved ones. */
export default function BudgetModal({ open, budget, onClose, onSave }) {
  const initial = {
    revenue_target: budget?.revenue?.target != null ? String(budget.revenue.target) : '',
    expense_limit: budget?.expenses?.target != null ? String(budget.expenses.target) : '',
  }
  return (
    <FormModal
      open={open}
      onClose={onClose}
      title="Set Budget"
      subtitle={budget?.period_label ? `Targets for ${budget.period_label}` : 'Targets for the current period'}
      submitLabel="Save Budget"
      initialValues={initial}
      fields={[
        { name: 'revenue_target', label: 'Revenue target (₹)', type: 'number', required: true, min: 0, placeholder: 'Target revenue for the period' },
        { name: 'expense_limit', label: 'Expense limit (₹)', type: 'number', required: true, min: 0, placeholder: 'Maximum spend for the period' },
      ]}
      onSubmit={onSave}
    />
  )
}
