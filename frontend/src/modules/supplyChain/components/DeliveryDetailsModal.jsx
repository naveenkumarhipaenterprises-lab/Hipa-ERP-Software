import { CircleCheck, Pencil, Truck } from 'lucide-react'
import { useState } from 'react'
import { supplyChainApi } from '../../../api/supplyChainApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatINR, formatNumber, todayISO } from '../../../utils/formatters'

const dash = (v) => (v === null || v === undefined || v === '' ? '—' : v)
const date = (v) => (v ? formatDate(v) : '—')
const iso = (v) => (v ? String(v).slice(0, 10) : '')

/**
 * One sales order's customer delivery: details, and (for `canManage`) edit expected date / tracking,
 * Dispatch (order -> In Transit) and Confirm Delivery (-> Delivered). Used by Supply Chain and Sales.
 * `onChanged` refreshes the caller's lists and figures after every change.
 */
export default function DeliveryDetailsModal({ orderId, canManage, onChanged, onClose }) {
  if (!orderId) return null
  return <DeliveryDetails orderId={orderId} canManage={canManage} onChanged={onChanged} onClose={onClose} />
}

function DeliveryDetails({ orderId, canManage, onChanged, onClose }) {
  const toast = useToast()
  const [form, setForm] = useState(null) // 'edit' | 'dispatch' | 'confirm'
  const detail = useApi(() => supplyChainApi.getCustomerDelivery(orderId), [orderId])
  const d = detail.data

  const done = (message) => {
    toast.success(message)
    detail.reload()
    onChanged?.()
  }
  const save = async (values) => {
    await supplyChainApi.updateCustomerDelivery(orderId, values)
    done(`Delivery details of ${d.order_number} saved`)
  }
  const dispatch = async (values) => {
    await supplyChainApi.dispatchOrder(orderId, values)
    done(`${d.order_number} dispatched`)
  }
  const confirm = async (values) => {
    await supplyChainApi.confirmDelivery(orderId, values)
    done(`${d.order_number} confirmed as delivered`)
  }

  const footer = d && canManage && (
    <>
      {d.can_edit && <Button variant="outline" icon={Pencil} onClick={() => setForm('edit')}>Edit Details</Button>}
      {d.can_dispatch && <Button icon={Truck} onClick={() => setForm('dispatch')}>Dispatch</Button>}
      {d.can_confirm && <Button icon={CircleCheck} onClick={() => setForm('confirm')}>Confirm Delivery</Button>}
    </>
  )

  return (
    <Modal open onClose={onClose} size="lg" title={d ? `Delivery of ${d.order_number}` : 'Customer Delivery'} subtitle={d?.customer} footer={footer || undefined}>
      {detail.error && !detail.loading ? (
        <ErrorMessage message={detail.error.message} onRetry={detail.reload} />
      ) : !d ? (
        <Loader label="Loading delivery…" />
      ) : (
        <div className="stack">
          <dl className="detail-grid">
            {[
              ['Delivery Status', <Badge key="s">{d.delivery_status}</Badge>],
              ['Order Status', d.order_status],
              ['Sales Order', d.order_number],
              ['Order Date', date(d.order_date)],
              ['Order Amount', d.amount != null ? formatINR(d.amount) : '—'],
              ['Expected Delivery', date(d.expected_delivery_date)],
              ['Dispatched On', date(d.dispatched_on)],
              ['Transporter / Vehicle', dash(d.carrier)],
              ['Tracking Reference', dash(d.tracking_reference)],
              ['Delivered On', date(d.delivered_on)],
              ['Received By', dash(d.received_by)],
              ['Confirmed By', d.confirmed_by ? `${d.confirmed_by}${d.confirmed_at ? `, ${formatDate(d.confirmed_at)}` : ''}` : '—'],
              ['Delivery Address', dash([d.delivery_address, d.city].filter(Boolean).join(', '))],
              ['Customer Phone', dash(d.customer_phone)],
              ['Products', Array.isArray(d.items) && d.items.length ? d.items.map((i) => `${i.product} (${formatNumber(i.quantity_kg)} kg)`).join(', ') : '—'],
              ['Notes', dash(d.notes)],
            ].map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
          {d.delivery_status === 'Delivered' && !d.confirmed_by && (
            <p className="muted">This order was marked Delivered before delivery confirmations were recorded.</p>
          )}
        </div>
      )}

      <FormModal
        open={form === 'edit'}
        onClose={() => setForm(null)}
        title={`Edit delivery of ${d?.order_number ?? ''}`}
        fields={[
          { name: 'expected_delivery_date', label: 'Expected delivery date', type: 'date' },
          { name: 'carrier', label: 'Transporter / vehicle', placeholder: 'e.g. lorry number or courier' },
          { name: 'tracking_reference', label: 'Tracking reference', placeholder: 'LR / docket / AWB number' },
          { name: 'notes', label: 'Notes', type: 'textarea', full: true },
        ]}
        initialValues={{ expected_delivery_date: iso(d?.expected_delivery_date), carrier: d?.carrier ?? '', tracking_reference: d?.tracking_reference ?? '', notes: d?.notes ?? '' }}
        onSubmit={save}
      />
      <FormModal
        open={form === 'dispatch'}
        onClose={() => setForm(null)}
        title={`Dispatch ${d?.order_number ?? ''}`}
        subtitle="The order moves to In Transit."
        fields={[
          { name: 'dispatched_on', label: 'Dispatched on', type: 'date', required: true, defaultValue: todayISO() },
          { name: 'expected_delivery_date', label: 'Expected delivery date', type: 'date' },
          { name: 'carrier', label: 'Transporter / vehicle' },
          { name: 'tracking_reference', label: 'Tracking reference' },
        ]}
        initialValues={{ expected_delivery_date: iso(d?.expected_delivery_date), carrier: d?.carrier ?? '', tracking_reference: d?.tracking_reference ?? '' }}
        submitLabel="Dispatch"
        onSubmit={dispatch}
      />
      <FormModal
        open={form === 'confirm'}
        onClose={() => setForm(null)}
        title={`Confirm delivery of ${d?.order_number ?? ''}`}
        subtitle="Confirm only when the customer has received the goods. Delivered is final."
        fields={[
          { name: 'delivered_on', label: 'Delivered on', type: 'date', required: true, defaultValue: todayISO() },
          { name: 'received_by', label: 'Received by', placeholder: 'Name of the person who received it' },
          { name: 'notes', label: 'Notes', type: 'textarea', full: true },
        ]}
        submitLabel="Confirm Delivered"
        onSubmit={confirm}
      />
    </Modal>
  )
}
