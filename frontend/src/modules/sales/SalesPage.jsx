import { BarChart3, Plus } from 'lucide-react'
import { useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { salesApi } from '../../api/salesApi'
import Button from '../../components/common/Button'
import DateRangeSelect from '../../components/common/DateRangeSelect'
import { Select } from '../../components/common/Input'
import PageHeader from '../../components/common/PageHeader'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { DATE_RANGES, NAV_ITEMS } from '../../utils/constants'
import InvoicesPanel from './components/InvoicesPanel'
import NewOrderModal from './components/NewOrderModal'
import OrdersPanel from './components/OrdersPanel'
import QuotationsPanel from './components/QuotationsPanel'
import SalesOverview from './components/SalesOverview'
import { ReceivePaymentModal, SalesPaymentsPanel, SalesReturnModal, SalesReturnsPanel } from './components/SalesRecords'

// Roles that may create quotations, orders, invoices and returns (the backend enforces the same rule)
const SALES_MANAGERS = ['admin', 'management', 'sales']
// Roles that may record customer payments
const PAYMENT_RECORDERS = ['admin', 'management', 'sales', 'finance']

// The Sales views from the sidebar sub-menu (Customers and Reports are their own modules)
const TABS = NAV_ITEMS.find((n) => n.key === 'sales').children.filter((c) => c.tab)

export default function SalesPage() {
  const { user } = useAuth()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [product, setProduct] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [record, setRecord] = useState(null) // { kind: 'payment' | 'return', invoice? }
  const justCreated = useRef(false)

  const canManage = SALES_MANAGERS.includes(user?.role)
  const canReceive = PAYMENT_RECORDERS.includes(user?.role)
  const tab = TABS.some((t) => t.tab === params.get('tab')) ? params.get('tab') : TABS[0].tab
  // ?new=order (e.g. from the dashboard's Quick Actions) opens the form
  const newOrderOpen = canManage && params.get('new') === 'order'
  const showFilters = tab === 'overview' || tab === 'orders'

  const options = useApi(() => salesApi.getOptions(), [refreshKey])
  const productOptions = Array.isArray(options.data?.products) ? options.data.products : []
  const rangeLabel = DATE_RANGES.find((r) => r.value === range)?.label ?? ''
  const refresh = () => setRefreshKey((k) => k + 1)

  const setParam = (patch) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k))
        return next
      },
      { replace: true },
    )

  const selectTab = (key) => setParam({ tab: key === TABS[0].tab ? null : key })

  const createOrder = async (values) => {
    const order = await salesApi.createOrder({ ...values, notes: values.notes?.trim() || undefined })
    toast.success(order?.order_number ? `Order ${order.order_number} created` : 'Order created')
    refresh()
    justCreated.current = true
  }

  // The form closes itself after a successful save; show the new order in the Orders tab
  const closeNewOrder = () => {
    setParam(justCreated.current ? { new: null, tab: 'orders' } : { new: null })
    justCreated.current = false
  }

  const savePayment = async (body) => {
    const p = await salesApi.createPayment(body)
    toast.success(`${p.receipt_number} recorded for ${p.invoice_number}`)
    refresh()
  }
  const saveReturn = async (body) => {
    const r = await salesApi.createReturn(body)
    toast.success(`Return ${r.return_number} recorded on ${r.invoice_number}`)
    refresh()
  }

  return (
    <div className="page">
      <title>Sales | HIPA MASALA</title>
      <PageHeader icon={BarChart3} title="Sales" subtitle="Quotations, orders, invoices, payments and returns, with sales performance">
        {showFilters && <DateRangeSelect value={range} onChange={setRange} />}
        {showFilters && (
          <Select
            className="field--inline"
            aria-label="Filter by product"
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            disabled={productOptions.length === 0}
            options={[{ value: '', label: 'All Products' }, ...productOptions.map((p) => ({ value: String(p.id), label: p.name }))]}
          />
        )}
        {canManage && (
          <Button icon={Plus} onClick={() => setParam({ new: 'order' })}>
            New Order
          </Button>
        )}
      </PageHeader>

      <div className="tabs" role="tablist" aria-label="Sales views">
        {TABS.map((t) => (
          <button
            key={t.tab}
            type="button"
            role="tab"
            id={`sales-tab-${t.tab}`}
            aria-selected={tab === t.tab}
            aria-controls="sales-tabpanel"
            className={`tabs__tab ${tab === t.tab ? 'tabs__tab--active' : ''}`}
            tabIndex={tab === t.tab ? 0 : -1}
            onClick={() => selectTab(t.tab)}
            onKeyDown={(e) => {
              if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
              const i = TABS.findIndex((x) => x.tab === tab)
              const next = TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length].tab
              selectTab(next)
              document.getElementById(`sales-tab-${next}`)?.focus()
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="stack" role="tabpanel" id="sales-tabpanel" aria-labelledby={`sales-tab-${tab}`}>
        {tab === 'overview' && <SalesOverview range={range} product={product} rangeLabel={rangeLabel} refreshKey={refreshKey} />}
        {tab === 'quotations' && <QuotationsPanel options={options} canManage={canManage} refreshKey={refreshKey} onChanged={refresh} />}
        {tab === 'orders' && (
          <OrdersPanel range={range} product={product} rangeLabel={rangeLabel} refreshKey={refreshKey} statuses={options.data?.statuses}
                       canManage={canManage} onChanged={refresh} />
        )}
        {tab === 'invoices' && (
          <InvoicesPanel options={options} canManage={canManage} canReceive={canReceive} refreshKey={refreshKey} onChanged={refresh}
                         onPay={(inv) => setRecord({ kind: 'payment', invoice: inv })} onReturn={(inv) => setRecord({ kind: 'return', invoice: inv })} />
        )}
        {tab === 'payments' && (
          <SalesPaymentsPanel options={options} canReceive={canReceive} refreshKey={refreshKey} onChanged={refresh} onNew={() => setRecord({ kind: 'payment' })} />
        )}
        {tab === 'returns' && (
          <SalesReturnsPanel options={options} canManage={canManage} refreshKey={refreshKey} onChanged={refresh} onNew={() => setRecord({ kind: 'return' })} />
        )}
      </div>

      <NewOrderModal open={newOrderOpen} onClose={closeNewOrder} options={options} onCreate={createOrder} />
      <ReceivePaymentModal open={record?.kind === 'payment'} invoice={record?.invoice} options={options} onClose={() => setRecord(null)} onSave={savePayment} />
      <SalesReturnModal open={record?.kind === 'return'} invoice={record?.invoice} options={options} onClose={() => setRecord(null)} onSave={saveReturn} />
    </div>
  )
}
