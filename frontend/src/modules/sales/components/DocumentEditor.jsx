import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import Button from '../../../components/common/Button'
import EmptyState from '../../../components/common/EmptyState'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Input, { Select, Textarea } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import TotalsSummary from '../../../components/common/TotalsSummary'
import { formatINR, todayISO } from '../../../utils/formatters'
import { documentTotals, lineTotals } from '../../../utils/money'
import { isEmail, isGstin } from '../../../utils/validation'

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''
const PARTY = ['customer_name', 'company_name', 'billing_address', 'shipping_address', 'phone', 'email', 'gstin']
const addDays = (iso, days) => {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() + Number(days))
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
let nextKey = 1
const blankLine = (gst = '') => ({ key: nextKey++, product_id: '', quantity_kg: '', unit_price: '', discount_pct: '', gst_pct: gst })

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
  const [lines, setLines] = useState(() =>
    doc ? list(doc.items).map((i) => ({ key: nextKey++, product_id: String(i.product_id), quantity_kg: i.quantity_kg, unit_price: i.unit_price,
                                        discount_pct: i.discount_pct, gst_pct: i.gst_pct }))
        : [blankLine(has(d.gst_pct) ? d.gst_pct : '')],
  )
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
  const setLine = (key, name, value) => setLines((ls) => ls.map((l) => (l.key === key ? { ...l, [name]: value } : l)))
  const priceOf = (l) => (has(l.unit_price) ? l.unit_price : products.find((p) => String(p.id) === String(l.product_id))?.price_per_kg ?? 0)
  const totals = documentTotals(lines.map((l) => ({ quantity: l.quantity_kg, unitPrice: priceOf(l), discountPct: l.discount_pct, gstPct: l.gst_pct })))

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
      const problems = []
      const seen = new Set()
      lines.forEach((l, i) => {
        const row = `Row ${i + 1}: `
        if (!l.product_id) problems.push(`${row}choose a product.`)
        else if (seen.has(l.product_id)) problems.push(`${row}this product is already on another line.`)
        seen.add(l.product_id)
        if (!(Number(l.quantity_kg) > 0)) problems.push(`${row}enter a quantity greater than 0.`)
        if (has(l.unit_price) && Number(l.unit_price) < 0) problems.push(`${row}the unit price can't be negative.`)
        for (const k of ['discount_pct', 'gst_pct']) if (has(l[k]) && (Number(l[k]) < 0 || Number(l[k]) > 100)) problems.push(`${row}percentages must be 0–100.`)
      })
      if (lines.length === 0) problems.push('Add at least one product.')
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
      ...(itemsLocked ? {} : {
        items: lines.map((l) => ({
          product_id: l.product_id, quantity_kg: Number(l.quantity_kg),
          ...(has(l.unit_price) ? { unit_price: Number(l.unit_price) } : {}),
          ...(has(l.discount_pct) ? { discount_pct: Number(l.discount_pct) } : {}),
          ...(has(l.gst_pct) ? { gst_pct: Number(l.gst_pct) } : {}),
        })),
      }),
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

        <div className="form-grid__full stack">
          <h3 className="doc-section">Products</h3>
          {itemsLocked && <p className="muted">This invoice was made from a sales order, so its products can't change.</p>}
          {errors.items && <ErrorMessage message={list(errors.items).join(' ')} />}
          <div className="lines">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th className="num">Quantity (kg)</th>
                  <th className="num">Unit price (₹)</th>
                  <th className="num">Discount %</th>
                  <th className="num">GST %</th>
                  <th className="num">Amount</th>
                  <th><span className="sr-only">Remove</span></th>
                </tr>
              </thead>
              <tbody>
                {lines.map((l, i) => {
                  const product = products.find((p) => String(p.id) === String(l.product_id))
                  const t = lineTotals(l.quantity_kg, priceOf(l), l.discount_pct, l.gst_pct)
                  return (
                    <tr key={l.key}>
                      <td style={{ minWidth: 220 }}>
                        <Select aria-label={`Product, row ${i + 1}`} value={l.product_id} disabled={itemsLocked} placeholder="Select product"
                                onChange={(e) => setLine(l.key, 'product_id', e.target.value)}
                                options={products.map((p) => ({ value: String(p.id), label: p.name }))} />
                      </td>
                      <td><Input aria-label={`Quantity, row ${i + 1}`} type="number" min="0" step="any" inputMode="decimal" value={l.quantity_kg} disabled={itemsLocked} onChange={(e) => setLine(l.key, 'quantity_kg', e.target.value)} /></td>
                      <td><Input aria-label={`Unit price, row ${i + 1}`} type="number" min="0" step="any" inputMode="decimal" value={l.unit_price} disabled={itemsLocked}
                                 placeholder={product ? String(product.price_per_kg) : ''} onChange={(e) => setLine(l.key, 'unit_price', e.target.value)} /></td>
                      <td><Input aria-label={`Discount percent, row ${i + 1}`} type="number" min="0" max="100" step="any" inputMode="decimal" value={l.discount_pct} disabled={itemsLocked} placeholder="0" onChange={(e) => setLine(l.key, 'discount_pct', e.target.value)} /></td>
                      <td><Input aria-label={`GST percent, row ${i + 1}`} type="number" min="0" max="100" step="any" inputMode="decimal" value={l.gst_pct} disabled={itemsLocked} placeholder="0" onChange={(e) => setLine(l.key, 'gst_pct', e.target.value)} /></td>
                      <td className="num lines__amount">{formatINR(t.total)}</td>
                      <td>
                        {!itemsLocked && (
                          <Button size="sm" variant="ghost" icon={Trash2} aria-label={`Remove row ${i + 1}`} disabled={lines.length === 1}
                                  onClick={() => setLines((ls) => ls.filter((x) => x.key !== l.key))} />
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {!itemsLocked && (
            <div>
              <Button size="sm" variant="soft" icon={Plus} onClick={() => setLines((ls) => [...ls, blankLine(has(d.gst_pct) ? d.gst_pct : '')])}>
                Add Product
              </Button>
            </div>
          )}
          <TotalsSummary totals={totals} totalLabel="Grand Total" />
        </div>

        <h3 className="doc-section form-grid__full">Terms</h3>
        {field('payment_terms', 'Payment terms', { className: quotation ? '' : 'form-grid__full' })}
        {quotation && field('delivery_terms', 'Delivery terms')}
        <Textarea className="form-grid__full" label="Notes" rows={2} value={form.notes} onChange={(e) => set('notes', e.target.value)} />
        <Textarea className="form-grid__full" label="Terms & conditions" rows={3} value={form.terms_conditions} onChange={(e) => set('terms_conditions', e.target.value)} />
      </form>
    </Modal>
  )
}
