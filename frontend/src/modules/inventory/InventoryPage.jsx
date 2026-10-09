import { BarChart3, ClipboardList, Download, IndianRupee, Package, PackageMinus, PackagePlus, Plus, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { inventoryApi } from '../../api/inventoryApi'
import DonutChart from '../../components/charts/DonutChart'
import SeriesChart from '../../components/charts/SeriesChart'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import DateRangeSelect from '../../components/common/DateRangeSelect'
import ErrorMessage from '../../components/common/ErrorMessage'
import FormModal from '../../components/common/FormModal'
import PageHeader from '../../components/common/PageHeader'
import { ActionsPanel, InsightPanel } from '../../components/dashboard/InsightPanel'
import QuickActions from '../../components/dashboard/QuickActions'
import StatCard from '../../components/dashboard/StatCard'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { CHART_COLORS, DATE_RANGES, hasAnyRole } from '../../utils/constants'
import { formatCompact, formatINR, formatKg, formatNumber } from '../../utils/formatters'
import InventoryItemsTable from './components/InventoryItemsTable'
import LowStockAlerts from './components/LowStockAlerts'
import MovementList from './components/MovementList'
import StockMovementModal from './components/StockMovementModal'

// Roles that may add products or record stock (the backend enforces the same rule)
const STOCK_MANAGERS = ['admin', 'management', 'inventory']

// Styling only: colour by status name
const STATUS_COLORS = { 'In Stock': '#1f9d55', 'Low Stock': '#f5b300', Critical: '#e5484d', 'Out of Stock': '#64748b' }

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''

const KPIS = [
  { key: 'total_stock_kg', label: 'Total Stock', icon: Package, tone: 'green', format: formatKg },
  { key: 'low_stock_items', label: 'Low Stock Items', icon: TriangleAlert, tone: 'red', format: formatNumber, sub: 'At or below reorder level' },
  { key: 'stock_value', label: 'Total Stock Value', icon: IndianRupee, tone: 'blue', format: formatINR },
  { key: 'active_products', label: 'Active Products', icon: ClipboardList, tone: 'yellow', format: formatNumber },
]

const ADD_ITEM_FIELDS = [
  { name: 'product_name', label: 'Product name', required: true, full: true, placeholder: 'Enter the product name' },
  { name: 'opening_stock_kg', label: 'Opening stock (kg)', type: 'number', min: 0, required: true },
  { name: 'price_per_kg', label: 'Value per kg (₹)', type: 'number', min: 0, required: true },
  { name: 'min_stock_kg', label: 'Minimum stock (kg)', type: 'number', min: 0, required: true },
  { name: 'reorder_level_kg', label: 'Reorder level (kg)', type: 'number', min: 0, required: true },
]

export default function InventoryPage() {
  const { user, can } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [modal, setModal] = useState(null) // 'add' | 'in' | 'out'
  const [refreshKey, setRefreshKey] = useState(0)
  const [downloading, setDownloading] = useState(false)

  const canManage = hasAnyRole(user, STOCK_MANAGERS)
  const overview = useApi(() => inventoryApi.getOverview({ range }), [range, refreshKey])
  const options = useApi(() => inventoryApi.getOptions(), [refreshKey])

  // Never show figures from another range or a failed request
  const loading = overview.loading
  const failed = Boolean(overview.error) && !loading
  const data = !loading && !failed ? (overview.data ?? {}) : null

  const stockLevels = list(data?.stock_levels).map((s) => ({ name: s.product, stock: Number(s.stock_kg) || 0 }))
  const statusCounts = list(data?.status_counts).map((s) => ({ name: s.status, value: Number(s.count) || 0 }))
  const statusTotal = statusCounts.reduce((sum, s) => sum + s.value, 0)
  const insights = data?.insights ?? {}

  const refresh = () => setRefreshKey((k) => k + 1)

  const addItem = async (values) => {
    const created = await inventoryApi.createItem({ ...values, product_name: values.product_name.trim() })
    toast.success(`${created?.product ?? values.product_name.trim()} added to inventory`)
    refresh()
  }

  const recordMovement = async (values) => {
    await inventoryApi.recordMovement(values)
    toast.success(values.type === 'in' ? 'Stock in recorded' : 'Stock out recorded')
    refresh()
  }

  const downloadReport = async () => {
    setDownloading(true)
    try {
      await inventoryApi.exportItems()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setDownloading(false)
    }
  }

  const actions = [
    ...(canManage
      ? [
          { label: 'Add Product', icon: Plus, tone: 'green', onClick: () => setModal('add') },
          { label: 'Stock In', icon: PackagePlus, tone: 'blue', onClick: () => setModal('in') },
          { label: 'Stock Out', icon: PackageMinus, tone: 'red', onClick: () => setModal('out') },
        ]
      : []),
    ...(can('reports') ? [{ label: 'View Reports', icon: BarChart3, tone: 'purple', onClick: () => navigate('/reports?type=inventory') }] : []),
  ]

  const skeleton = <div className="skeleton skeleton--chart-inner" aria-label="Loading" />

  return (
    <div className="page">
      <title>Inventory | HIPA MASALA</title>
      <PageHeader icon={Package} title="Inventory" subtitle="Real-time stock levels, usage and inventory analytics">
        <DateRangeSelect value={range} onChange={setRange} />
        <Button variant="outline" icon={Download} onClick={downloadReport} loading={downloading}>
          Download Report
        </Button>
        {canManage && (
          <Button icon={Plus} onClick={() => setModal('add')}>
            Add Product
          </Button>
        )}
      </PageHeader>

      {failed && <ErrorMessage message={overview.error.message} onRetry={refresh} />}

      {!failed && (
        <>
          <div className="kpi-grid kpi-grid--auto">
            {KPIS.map((k) => {
              const kpi = data?.kpis?.[k.key]
              return (
                <StatCard
                  key={k.key}
                  icon={k.icon}
                  tone={k.tone}
                  label={k.label}
                  loading={loading}
                  value={has(kpi?.value) ? k.format(kpi.value) : null}
                  change={kpi?.change}
                  changeLabel="vs prev. period"
                  sub={k.sub}
                  valueTone={k.key === 'low_stock_items' && Number(kpi?.value) > 0 ? 'red' : undefined}
                />
              )
            })}
          </div>

          <div className="dash-row">
            <Card title="Stock Level Overview" subtitle="Current stock (kg)" className="dash-row__wide">
              {loading ? (
                skeleton
              ) : (
                <SeriesChart
                  data={stockLevels}
                  xKey="name"
                  series={[{ key: 'stock', name: 'Stock', color: CHART_COLORS[0], type: 'bar' }]}
                  barColors={CHART_COLORS}
                  barLabels
                  xInterval={0}
                  yFormatter={formatCompact}
                  tooltipFormatter={(v) => formatKg(v)}
                  height={250}
                  emptyTitle="No stock recorded"
                  emptyMessage="Stock levels will appear once products are added."
                />
              )}
            </Card>
            <Card title="Stock Status">
              {loading ? (
                skeleton
              ) : (
                <DonutChart
                  data={statusCounts}
                  colors={STATUS_COLORS}
                  centerValue={formatNumber(statusTotal)}
                  centerLabel="Products"
                  valueFormatter={(v) => formatNumber(v)}
                  size={160}
                  emptyTitle="No products yet"
                  emptyMessage="The split by stock status will appear here."
                />
              )}
            </Card>
            {actions.length > 0 && (
              <Card title="Quick Actions">
                <QuickActions layout="stack" actions={actions} columns={2} />
              </Card>
            )}
          </div>
        </>
      )}

      {/* When the overview fails its banner covers the page; Retry reloads the table too */}
      {!failed && (
        <div className="grid-main-side">
          <InventoryItemsTable refreshKey={refreshKey} statuses={options.data?.statuses} canManage={canManage} onChanged={refresh} />
          <div className="stack">
            <Card title="Low Stock Alerts">
              {loading ? <div className="skeleton skeleton--list" aria-label="Loading" /> : <LowStockAlerts items={data?.low_stock} />}
            </Card>
            <Card title="Recent Inventory Movements">
              {loading ? <div className="skeleton skeleton--list" aria-label="Loading" /> : <MovementList items={data?.movements} />}
            </Card>
          </div>
        </div>
      )}

      {!failed && (
        <div className="grid-2">
          <InsightPanel
            title="AI Inventory Insight"
            text={loading ? undefined : insights.text}
            emptyText={loading ? 'Loading insights…' : undefined}
          />
          <ActionsPanel items={loading ? undefined : list(insights.actions)} emptyText={loading ? 'Loading…' : undefined} />
        </div>
      )}

      <FormModal
        open={modal === 'add'}
        onClose={() => setModal(null)}
        title="Add Product"
        subtitle="Add a new product to inventory"
        fields={ADD_ITEM_FIELDS}
        submitLabel="Add Product"
        onSubmit={addItem}
      />
      <StockMovementModal
        type={modal === 'in' || modal === 'out' ? modal : null}
        onClose={() => setModal(null)}
        options={options}
        onSubmit={recordMovement}
      />
    </div>
  )
}
