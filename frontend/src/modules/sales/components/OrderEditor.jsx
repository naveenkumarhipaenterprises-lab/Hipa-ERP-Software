import { useState } from 'react'
import { salesApi } from '../../../api/salesApi'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Input, { Textarea } from '../../../components/common/Input'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { useApi } from '../../../hooks/useApi'
import { todayISO } from '../../../utils/formatters'
import { has, linesBody, linesFromItems, linesProblems } from '../lines'
import ProductLines from './ProductLines'

const list = (v) => (Array.isArray(v) ? v : [])

/**
 * Edit a pending sales order that isn't invoiced (PATCH /sales/orders/<id>/): products, quantities, prices, discount,
 * GST, order date and notes. The server puts the old quantities back into stock and takes the new ones out; the
 * customer can't change (cancel the order and create a new one).
 */
export default function OrderEditor({ order, options, onClose, onSaved }) {
  const detail = useApi(() => (order ? salesApi.getOrder(order.id) : Promise.resolve(null)), [order?.id])
  if (!order) return null
  const title = `Edit Order ${order.order_number ?? ''}`
  if (detail.error && !detail.loading) {
    return (
      <Modal open onClose={onClose} title={title} size="sm">
        <ErrorMessage message={detail.error.message} onRetry={detail.reload} />
      </Modal>
    )
  }
  if (!detail.data) {
    return (
      <Modal open onClose={onClose} title={title} size="sm">
        <Loader label="Loading order…" />
      </Modal>
    )
  }
  return (
    <OptionsGate options={options} title={title} onClose={onClose} loadingLabel="Loading products…">
      {(data) => <Editor title={title} order={detail.data} data={data} onClose={onClose} onSaved={onSaved} />}
    </OptionsGate>
  )
}

function Editor({ title, order, data, onClose, onSaved }) {
  const defaults = data.defaults ?? {}
  // Products switched off since the order was made still show on its own lines
  const products = [...list(data.products)]
  for (const i of list(order.items)) {
    if (!products.some((p) => String(p.id) === String(i.product_id))) products.push({ id: i.product_id, name: i.product, price_per_kg: i.unit_price })
  }
  const [lines, setLines] = useState(() => linesFromItems(order.items))
  const [orderDate, setOrderDate] = useState(order.date ?? '')
  const [notes, setNotes] = useState(order.notes ?? '')
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState(null)
  const [pending, setPending] = useState(false)

  const submit = async (ev) => {
    ev.preventDefault()
    const e = {}
    if (!orderDate) e.order_date = 'Order date is required'
    else if (orderDate > todayISO()) e.order_date = "Can't be in the future"
    const problems = linesProblems(lines)
    if (problems.length) e.items = problems
    setErrors(e)
    if (Object.keys(e).length) return
    setPending(true)
    setSubmitError(null)
    try {
      const saved = await salesApi.updateOrder(order.id, { order_date: orderDate, notes, items: linesBody(lines) })
      onSaved(saved)
      onClose()
    } catch (err) {
      const fieldErrs = {}
      for (const [k, v] of Object.entries(err.fields ?? {})) {
        if (k !== 'detail') fieldErrs[k] = k === 'items' ? list(v) : Array.isArray(v) ? v[0] : v
      }
      setErrors(fieldErrs)
      setSubmitError(Object.keys(fieldErrs).length ? null : err.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      subtitle={`${order.customer} · Changing products or quantities updates the stock. To change the customer, cancel the order and create a new one.`}
      size="xl"
      closeOnBackdrop={false}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="order-editor" loading={pending}>Save Order</Button>
        </>
      }
    >
      <form id="order-editor" className="form-grid" onSubmit={submit} noValidate>
        {submitError && <ErrorMessage message={submitError} className="form-grid__full" />}
        <Input label="Order date *" type="date" value={orderDate} error={errors.order_date} max={todayISO()}
               onChange={(e) => { setOrderDate(e.target.value); setErrors((x) => ({ ...x, order_date: undefined })) }} />
        <ProductLines lines={lines} onChange={setLines} products={products} errors={errors.items}
                      defaultGst={has(defaults.gst_pct) ? defaults.gst_pct : ''} />
        <Textarea className="form-grid__full" label="Notes" rows={2} maxLength={500} value={notes} error={errors.notes}
                  onChange={(e) => setNotes(e.target.value)} />
      </form>
    </Modal>
  )
}
