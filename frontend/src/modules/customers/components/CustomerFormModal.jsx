import FormModal from '../../../components/common/FormModal'
import OptionsGate from '../../../components/common/OptionsGate'

const list = (v) => (Array.isArray(v) ? v : [])

/**
 * Add (POST /customers/) or edit (PATCH /customers/<id>/) a customer.
 * Customer types and statuses come from GET /customers/options/.
 */
export default function CustomerFormModal({ open, customer, options, onClose, onSave }) {
  if (!open) return null
  const editing = Boolean(customer)
  return (
    <OptionsGate options={options} title={editing ? 'Edit Customer' : 'Add Customer'} onClose={onClose}>
      {(data) => {
        const fields = [
          { name: 'name', label: 'Customer name', required: true, full: true, placeholder: 'Business or customer name' },
          { name: 'type', label: 'Customer type', type: 'select', required: true, options: list(data.types), placeholder: 'Select type' },
          { name: 'city', label: 'City', required: true, placeholder: 'City or town' },
          { name: 'contact_person', label: 'Contact person', placeholder: 'Name of the main contact' },
          { name: 'phone', label: 'Mobile number', type: 'tel', placeholder: '10-digit mobile number' },
          { name: 'email', label: 'Email', type: 'email', full: true, placeholder: 'name@business.com' },
          { name: 'address', label: 'Address', type: 'textarea' },
        ]
        if (editing && list(data.statuses).length) {
          fields.splice(2, 0, { name: 'status', label: 'Status', type: 'select', required: true, options: data.statuses })
        }
        const initial = editing
          ? Object.fromEntries(fields.map((f) => [f.name, customer[f.name] == null ? '' : String(customer[f.name])]))
          : {}

        const submit = (values) => {
          // Blank optional fields are sent as empty strings so an edit can clear them
          const body = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, typeof v === 'string' ? v.trim() : v]))
          // "98765 43210" / "98765-43210" -> "9876543210" (a leading +91 is kept)
          if (body.phone) body.phone = body.phone.replace(/[\s-]/g, '')
          return onSave(body)
        }

        return (
          <FormModal
            open
            onClose={onClose}
            title={editing ? 'Edit Customer' : 'Add Customer'}
            subtitle={editing ? customer.name : 'Create a new customer record'}
            fields={fields}
            initialValues={initial}
            submitLabel={editing ? 'Save Changes' : 'Add Customer'}
            onSubmit={submit}
          />
        )
      }}
    </OptionsGate>
  )
}
