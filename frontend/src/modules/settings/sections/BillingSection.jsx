import { settingsApi } from '../../../api/settingsApi'
import SettingsForm from '../components/SettingsForm'

const pct = (label) => ({ name: label.name, label: label.text, type: 'number', placeholder: 'e.g. 5',
  validate: (v) => (v !== '' && (Number(v) < 0 || Number(v) > 100) ? 'Enter 0–100' : undefined) })
const days = (name, label, placeholder, min = 0) => ({ name, label, type: 'number', placeholder,
  validate: (v) => (v !== '' && (Number(v) < min || Number(v) > 365 || !Number.isInteger(Number(v))) ? `Enter whole days, ${min}–365` : undefined) })

/**
 * Settings → Tax & Billing: defaults for GST, quotations, invoices (with bank details printed on them) and purchases.
 * Everything starts empty; nothing is assumed until an admin fills it in. Each card saves only its own fields.
 */
export default function BillingSection() {
  const load = settingsApi.getBilling
  const save = (values) => settingsApi.saveBilling(values)
  return (
    <div className="stack">
      <SettingsForm
        title="Tax / GST"
        subtitle="Default GST rates filled into new product lines (each line can be changed)"
        load={load}
        save={save}
        successMessage="Tax settings saved"
        fields={[pct({ name: 'default_sales_gst_pct', text: 'GST % on sales' }), pct({ name: 'default_purchase_gst_pct', text: 'GST % on purchases' })]}
      />
      <SettingsForm
        title="Quotations"
        subtitle="Defaults for new quotations"
        load={load}
        save={save}
        successMessage="Quotation settings saved"
        fields={[
          days('quotation_validity_days', 'Valid for (days)', 'e.g. 15', 1),
          { name: 'quotation_payment_terms', label: 'Payment terms', placeholder: 'e.g. 50% advance, balance on delivery' },
          { name: 'quotation_delivery_terms', label: 'Delivery terms', full: true, placeholder: 'e.g. Ex-works, within 7 days of confirmation' },
          { name: 'quotation_terms', label: 'Terms & conditions', type: 'textarea' },
        ]}
      />
      <SettingsForm
        title="Invoices"
        subtitle="Defaults for new invoices, and the bank details and signatory printed on invoice PDFs"
        load={load}
        save={save}
        successMessage="Invoice settings saved"
        fields={[
          days('invoice_due_days', 'Payment due after (days)', 'e.g. 30'),
          { name: 'invoice_payment_terms', label: 'Payment terms', placeholder: 'e.g. Net 30 days' },
          { name: 'invoice_terms', label: 'Terms & conditions', type: 'textarea' },
          { name: 'bank_name', label: 'Bank name' },
          { name: 'bank_account_name', label: 'Account name' },
          { name: 'bank_account_number', label: 'Account number', validate: (v) => (v && !/^\d{6,20}$/.test(v) ? 'Digits only (6–20)' : undefined) },
          { name: 'bank_ifsc', label: 'IFSC', placeholder: '11 characters', validate: (v) => (v && !/^[A-Za-z]{4}0[A-Za-z0-9]{6}$/.test(v) ? 'Enter a valid IFSC code' : undefined) },
          { name: 'upi_id', label: 'UPI ID', placeholder: 'name@bank' },
          { name: 'authorised_signatory', label: 'Authorised signatory', placeholder: 'Name printed under the signature' },
        ]}
      />
      <SettingsForm
        title="Purchase & Suppliers"
        subtitle="Used when a supplier has no credit days of its own"
        load={load}
        save={save}
        successMessage="Purchase settings saved"
        fields={[days('default_supplier_credit_days', 'Supplier credit days', 'e.g. 30')]}
      />
    </div>
  )
}
