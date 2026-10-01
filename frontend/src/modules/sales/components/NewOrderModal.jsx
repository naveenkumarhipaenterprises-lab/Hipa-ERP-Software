import { UserPlus } from 'lucide-react'
import { Link } from 'react-router-dom'
import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'

const toOptions = (items) => (Array.isArray(items) ? items : []).map((x) => ({ value: String(x.id), label: x.name }))


/**
 * Creates an order via POST /sales/orders/. Customer and product choices come from
 * GET /sales/options/ (passed in as `options`); nothing is pre-filled except today's date.
 */
export default function NewOrderModal({ open, onClose, options, onCreate }) {
  if (!open) return null
  return (
    <OptionsGate options={options} title="New Order" onClose={onClose} loadingLabel="Loading customers and products…">
      {(data) => <NewOrderForm data={data} onClose={onClose} onCreate={onCreate} />}
    </OptionsGate>
  )
}

function NewOrderForm({ data, onClose, onCreate }) {
  const customers = toOptions(data.customers)
  const products = toOptions(data.products)

  if (customers.length === 0 || products.length === 0) {
    return (
      <Modal open onClose={onClose} title="New Order" size="sm">
        <EmptyState
          compact
          icon={UserPlus}
          title={customers.length === 0 ? 'No customers yet' : 'No products yet'}
          message={
            customers.length === 0
              ? 'Add a customer before creating an order.'
              : 'Products must be set up before orders can be created. Contact your administrator.'
          }
          action={
            customers.length === 0 && (
              <Link to="/customers?new=customer" className="btn btn--primary btn--md">
                Add Customer
              </Link>
            )
          }
        />
      </Modal>
    )
  }

  return (
    <FormModal
      open
      onClose={onClose}
      title="New Order"
      subtitle="The order amount is calculated by the system from current prices."
      submitLabel="Create Order"
      initialValues={{ order_date: todayISO() }}
      fields={[
        { name: 'customer_id', label: 'Customer', type: 'select', options: customers, required: true, placeholder: 'Select customer' },
        { name: 'product_id', label: 'Product', type: 'select', options: products, required: true, placeholder: 'Select product' },
        { name: 'quantity_kg', label: 'Quantity (kg)', type: 'number', required: true, min: 0.01, placeholder: 'Enter quantity in kg' },
        { name: 'order_date', label: 'Order Date', type: 'date', required: true },
        { name: 'notes', label: 'Notes', type: 'textarea', placeholder: 'Delivery instructions, reference number…' },
      ]}
      onSubmit={onCreate}
    />
  )
}
