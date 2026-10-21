import { useState } from 'react'
import { Link } from 'react-router-dom'
import Button from '../../../components/common/Button'
import EmptyState from '../../../components/common/EmptyState'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Input, { Select, Textarea } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { todayISO } from '../../../utils/formatters'
import { isEmail, isGstin } from '../../../utils/validation'
import { blankLine, has, linesBody, linesFromItems, linesProblems } from '../lines'
import ProductLines from './ProductLines'

const list = (v) => (Array.isArray(v) ? v : [])
const PARTY = ['customer_name', 'company_name', 'billing_address', 'shipping_address', 'phone', 'email', 'gstin']
const addDays = (iso, days) => {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() + Number(days))
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * Create / edit a quotation or a sales invoice: customer details (picked from the customer database or typed),
 * product lines with add / remove, and totals that update as you type. The saved totals come from the backend.
 * kind: 'quotation' | 'invoice'. `document` is the API detail when editing. `itemsLocked` keeps the lines read-only
 * (an invoice made from a sales order).
 */
export default function DocumentEditor({ open, kind, document, options, onClose, onSave }) {
  if (!open) return null
  const title = `${document ? 'Edit' : 'New'} ${kind === 'quotation' ? 'Quotation' : 'Sales Invoice'}`
  return (
    <OptionsGate options={options} title={title} onClose={onClose} loadingLabel="Loading customers and products…">
      {(data) =>
        list(data.products).length === 0 ? (
          <Modal open onClose={onClose} title={title} size="sm">
            <EmptyState compact title="No products yet" message="Add products in Inventory before creating quotations or invoices." />
          </Modal>
        ) : (
          <Editor kind={kind} title={title} document={document} data={data} onClose={onClose} onSave={onSave} />
        )
      }
    </OptionsGate>
  )
}

function Editor({ kind, title, document: doc, data, onClose, onSave }) {
  const quotation = kind === 'quotation'
  const d = data.defaults ?? {}
  const products = list(data.products)
  const customers = list(data.customers)
  const itemsLocked = Boolean(doc && doc.can_edit_items === false)
  const today = todayISO()

  const [form, setForm] = useState(() => {
    if (doc) return { customer_id: doc.customer_id ? String(doc.customer_id) : '', ...Object.fromEntries(PARTY.map((k) => [k, doc[k] ?? ''])),
                      quotation_date: doc.quotation_date ?? '', valid_until: doc.valid_until ?? '', invoice_date: doc.invoice_date ?? '',
                      due_date: doc.due_date ?? '', payment_terms: doc.payment_terms ?? '', delivery_terms: doc.delivery_terms ?? '',
                      notes: doc.notes ?? '', terms_conditions: doc.terms_conditions ?? '' }
    return {
      customer_id: '', ...Object.fromEntries(PARTY.map((k) => [k, ''])),
      quotation_date: today, valid_until: has(d.quotation_validity_days) ? addDays(today, d.quotation_validity_days) : '',
      invoice_date: today, due_date: has(d.invoice_due_days) ? addDays(today, d.invoice_due_days) : '',
      payment_terms: (quotation ? d.quotation_payment_terms : d.invoice_payment_terms) ?? '',
      delivery_terms: d.quotation_delivery_terms ?? '', notes: '',
      terms_conditions: (quotation ? d.quotation_terms : d.invoice_terms) ?? '',
    }
  })
  const [lines, setLines] = useState(() => (doc ? linesFromItems(doc.items) : [blankLine(has(d.gst_pct) ? d.gst_pct : '')]))
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState(null)
  const [pending, setPending] = useState(false)

  const set = (name, value) => {
    setForm((f) => ({ ...f, [name]: value }))
    setErrors((e) => ({ ...e, [name]: undefined }))
  }
  const pickCustomer = (id) => {
    const c = customers.find((x) => String(x.id) === id)
    setForm((f) => ({
      ...f, customer_id: id,
      ...(c ? { customer_name: c.name, billing_address: c.address ?? '', shipping_address: c.shipping_address || c.address || '',
                phone: c.phone ?? '', email: c.email ?? '', gstin: c.gstin ?? '' } : {}),
    }))
    setErrors((e) => ({ ...e, customer_id: undefined, customer_name: undefined }))
  }

  const validate = () => {
    const e = {}
    if (!form.customer_name.trim()) e.customer_name = 'Choose a customer or enter the customer name'
    if (!quotation && !form.customer_id) e.customer_id = 'Choose a customer for the invoice'
    if (form.email && !isEmail(form.email)) e.email = 'Enter a valid email address'
    if (form.gstin && !isGstin(form.gstin)) e.gstin = 'Enter a valid 15-character GSTIN'
    if (quotation) {
      if (!form.quotation_date) e.quotation_date = 'Quotation date is required'
      else if (form.quotation_date > today) e.quotation_date = "Can't be in the future"
      if (!form.valid_until) e.valid_until = 'Valid until is required'
      else if (form.valid_until < (form.quotation_date || today) || (!doc && form.valid_until < today)) e.valid_until = "Can't be in the past or before the quotation date"
    } else {
      if (!doc && form.invoice_date > today) e.invoice_date = "Can't be in the future"
      if (form.due_date && form.due_date < (form.invoice_date || today)) e.due_date = "Can't be before the invoice date"
    }
    if (!itemsLocked) {
      const problems = linesProblems(lines)
      if (problems.length) e.items = problems
    }
    return e
  }

  const submit = async (ev) => {
    ev.preventDefault()
    const e = validate()
    setErrors(e)
    if (Object.keys(e).length) return
    const body = {
      ...(form.customer_id || !doc ? { customer_id: form.customer_id || undefined } : {}),
      ...Object.fromEntries(PARTY.map((k) => [k, form[k].trim()])),
      payment_terms: form.payment_terms, notes: form.notes, terms_conditions: form.terms_conditions,
      ...(quotation
        ? { quotation_date: form.quotation_date, valid_until: form.valid_until, delivery_terms: form.delivery_terms }
        : { ...(doc ? {} : { invoice_date: form.invoice_date }), due_date: form.due_date || null }),
      ...(itemsLocked ? {} : { items: linesBody(lines) }),
    }
    setPending(true)
    setSubmitError(null)
    try {
      await onSave(body)
      onClose()
    } catch (err) {
      const fieldErrs = {}
      for (const [k, v] of Object.entries(err.fields ?? {})) fieldErrs[k] = k === 'items' ? list(v) : Array.isArray(v) ? v[0] : v
      setErrors(fieldErrs)
      setSubmitError(Object.keys(fieldErrs).length ? null : err.message)
    } finally {
      setPending(false)
    }
  }

  const field = (name, label, props = {}) => (
    <Input label={label} value={form[name]} error={errors[name]} onChange={(e) => set(name, e.target.value)} {...props} />
  )

  return (
    <Modal
      open
      onClose={onClose}
      title={doc ? `${title} ${doc.quotation_number ?? doc.invoice_number ?? ''}` : title}
      subtitle={quotation ? 'A quotation is not an invoice. Convert it once the customer accepts.' : 'The invoice number is assigned automatically.'}
      size="xl"
      closeOnBackdrop={false}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="document-editor" loading={pending}>{quotation ? 'Save Quotation' : 'Save Invoice'}</Button>
        </>
      }
    >
      <form id="document-editor" className="form-grid" onSubmit={submit} noValidate>
        {submitError && <ErrorMessage message={submitError} className="form-grid__full" />}

        <h3 className="doc-section form-grid__full">Customer</h3>
        <Select
          label={quotation ? 'Existing customer' : 'Customer *'}
          className="form-grid__full"
          value={form.customer_id}
          error={errors.customer_id}
          onChange={(e) => pickCustomer(e.target.value)}
          placeholder={quotation ? 'New customer (type the details below)' : 'Select customer'}
          options={customers.map((c) => ({ value: String(c.id), label: c.city ? `${c.name} (${c.city})` : c.name }))}
          hint={customers.length === 0 ? <Link to="/customers?new=customer">Add a customer</Link> : undefined}
        />
        {field('customer_name', 'Customer name *')}
        {field('company_name', 'Company name')}
        <Textarea label="Billing address" rows={2} value={form.billing_address} onChange={(e) => set('billing_address', e.target.value)} />
        <Textarea label="Shipping address" rows={2} value={form.shipping_address} placeholder="Same as billing when empty" onChange={(e) => set('shipping_address', e.target.value)} />
        {field('phone', 'Phone')}
        {field('email', 'Email', { type: 'email' })}
        {field('gstin', 'GSTIN', { placeholder: 'Where applicable' })}

        <h3 className="doc-section form-grid__full">{quotation ? 'Quotation' : 'Invoice'}</h3>
        {quotation ? (
          <>
            {field('quotation_date', 'Quotation date *', { type: 'date' })}
            {field('valid_until', 'Valid until *', { type: 'date' })}
          </>
        ) : (
          <>
            {field('invoice_date', 'Invoice date *', { type: 'date', disabled: Boolean(doc) })}
            {field('due_date', 'Due date', { type: 'date' })}
          </>
        )}

        <ProductLines lines={lines} onChange={setLines} products={products} defaultGst={has(d.gst_pct) ? d.gst_pct : ''}
                      locked={itemsLocked} lockedNote="This invoice was made from a sales order, so its products can't change."
                      errors={errors.items} />

        <h3 className="doc-section form-grid__full">Terms</h3>
        {field('payment_terms', 'Payment terms', { className: quotation ? '' : 'form-grid__full' })}
        {quotation && field('delivery_terms', 'Delivery terms')}
        <Textarea className="form-grid__full" label="Notes" rows={2} value={form.notes} onChange={(e) => set('notes', e.target.value)} />
        <Textarea className="form-grid__full" label="Terms & conditions" rows={3} value={form.terms_conditions} onChange={(e) => set('terms_conditions', e.target.value)} />
      </form>
    </Modal>
  )
}
