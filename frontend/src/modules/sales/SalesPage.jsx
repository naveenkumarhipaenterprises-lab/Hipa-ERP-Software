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
import { DATE_RANGES } from '../../utils/constants'
import NewOrderModal from './components/NewOrderModal'
import OrdersPanel from './components/OrdersPanel'
import SalesOverview from './components/SalesOverview'

// Roles that may create or cancel orders (the backend enforces the same rule)
const ORDER_MANAGERS = ['admin', 'management', 'sales']

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'orders', label: 'Orders' },
]

export default function SalesPage() {
  const { user } = useAuth()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [product, setProduct] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const justCreated = useRef(false)

  const canManage = ORDER_MANAGERS.includes(user?.role)
  const tab = params.get('tab') === 'orders' ? 'orders' : 'overview'
  // ?new=order (e.g. from the dashboard's Quick Actions) opens the form
  const newOrderOpen = canManage && params.get('new') === 'order'

  const options = useApi(() => salesApi.getOptions(), [])
  const productOptions = Array.isArray(options.data?.products) ? options.data.products : []
  const rangeLabel = DATE_RANGES.find((r) => r.value === range)?.label ?? ''

  const setParam = (patch) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k))
        return next
      },
      { replace: true },
    )

  const selectTab = (key) => setParam({ tab: key === 'overview' ? null : key })

  const createOrder = async (values) => {
    const order = await salesApi.createOrder({ ...values, notes: values.notes?.trim() || undefined })
    toast.success(order?.order_number ? `Order ${order.order_number} created` : 'Order created')
    setRefreshKey((k) => k + 1)
    justCreated.current = true
  }

  // The form closes itself after a successful save; show the new order in the Orders tab
  const closeNewOrder = () => {
    setParam(justCreated.current ? { new: null, tab: 'orders' } : { new: null })
    justCreated.current = false
  }

  return (
    <div className="page">
      <title>Sales | HIPA MASALA</title>
      <PageHeader icon={BarChart3} title="Sales" subtitle="Track sales performance, customer insights and growth trends">
        <DateRangeSelect value={range} onChange={setRange} />
        <Select
          className="field--inline"
          aria-label="Filter by product"
          value={product}
          onChange={(e) => setProduct(e.target.value)}
          disabled={productOptions.length === 0}
          options={[{ value: '', label: 'All Products' }, ...productOptions.map((p) => ({ value: String(p.id), label: p.name }))]}
        />
        {canManage && (
          <Button icon={Plus} onClick={() => setParam({ new: 'order' })}>
            New Order
          </Button>
        )}
      </PageHeader>

      <div className="tabs" role="tablist" aria-label="Sales views">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            id={`sales-tab-${t.key}`}
            aria-selected={tab === t.key}
            aria-controls="sales-tabpanel"
            className={`tabs__tab ${tab === t.key ? 'tabs__tab--active' : ''}`}
            tabIndex={tab === t.key ? 0 : -1}
            onClick={() => selectTab(t.key)}
            onKeyDown={(e) => {
              if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
              const i = TABS.findIndex((x) => x.key === tab)
              const next = TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length].key
              selectTab(next)
              document.getElementById(`sales-tab-${next}`)?.focus()
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="stack" role="tabpanel" id="sales-tabpanel" aria-labelledby={`sales-tab-${tab}`}>
        {tab === 'overview' ? (
          <SalesOverview range={range} product={product} rangeLabel={rangeLabel} refreshKey={refreshKey} />
        ) : (
          <OrdersPanel
            range={range}
            product={product}
            rangeLabel={rangeLabel}
            refreshKey={refreshKey}
            statuses={options.data?.statuses}
            canManage={canManage}
            onChanged={() => setRefreshKey((k) => k + 1)}
          />
        )}
      </div>

      <NewOrderModal open={newOrderOpen} onClose={closeNewOrder} options={options} onCreate={createOrder} />
    </div>
  )
}
