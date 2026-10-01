import { Clock, IndianRupee, Leaf, PackageCheck, Plus, Timer, Truck, Users } from 'lucide-react'
import { useState } from 'react'
import { supplyChainApi } from '../../api/supplyChainApi'
import DonutChart from '../../components/charts/DonutChart'
import SeriesChart from '../../components/charts/SeriesChart'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import DateRangeSelect, { MiniSelect } from '../../components/common/DateRangeSelect'
import ErrorMessage from '../../components/common/ErrorMessage'
import PageHeader from '../../components/common/PageHeader'
import Table from '../../components/common/Table'
import { ActionsPanel, InsightPanel } from '../../components/dashboard/InsightPanel'
import QuickActions from '../../components/dashboard/QuickActions'
import StatCard from '../../components/dashboard/StatCard'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { CHART_COLORS, DATE_RANGES } from '../../utils/constants'
import { formatINR, formatKg, formatNumber, formatPercent } from '../../utils/formatters'
import AlertFeed from './components/AlertFeed'
import PurchaseOrderModal from './components/PurchaseOrderModal'
import { SHIPMENT_COLUMNS } from './components/shipmentColumns'
import ShipmentsModal from './components/ShipmentsModal'
import SuppliersModal from './components/SuppliersModal'
import SupplyFlow from './components/SupplyFlow'

// Roles that may raise purchase orders and add suppliers (the backend enforces the same rule)
const SUPPLY_MANAGERS = ['admin', 'management', 'inventory']

const PERFORMANCE_MONTHS = [
  { value: '6', label: 'Last 6 Months' },
  { value: '3', label: 'Last 3 Months' },
]

const KPIS = [
  { key: 'total_suppliers', label: 'Total Suppliers', icon: Leaf, tone: 'green', format: formatNumber },
  { key: 'active_shipments', label: 'Active Shipments', icon: PackageCheck, tone: 'blue', format: formatNumber },
  { key: 'on_time_delivery_pct', label: 'On-Time Delivery', icon: Clock, tone: 'teal', format: (v) => formatPercent(v, 1) },
  { key: 'procurement_cost', label: 'Procurement Cost', icon: IndianRupee, tone: 'orange', format: formatINR, goodWhenDown: true },
  { key: 'pending_orders', label: 'Pending Orders', icon: Timer, tone: 'yellow', format: formatNumber, goodWhenDown: true },
]

// Styling only: colour per shipment status
const SHIPMENT_STATUS = [
  { key: 'in_transit', label: 'In Transit', color: '#2f6fde' },
  { key: 'delivered', label: 'Delivered', color: '#1f9d55' },
  { key: 'delayed', label: 'Delayed', color: '#e5484d' },
]

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''

export default function SupplyChainPage() {
  const { user } = useAuth()
  const toast = useToast()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [months, setMonths] = useState(PERFORMANCE_MONTHS[0].value)
  const [modal, setModal] = useState(null) // 'po' | 'shipments' | 'suppliers'
  const [refreshKey, setRefreshKey] = useState(0)

  const canManage = SUPPLY_MANAGERS.includes(user?.role)
  const overview = useApi(() => supplyChainApi.getOverview({ range }), [range, refreshKey])
  const performance = useApi(() => supplyChainApi.getSupplierPerformance({ months }), [months, refreshKey])
  const options = useApi(() => supplyChainApi.getOptions(), [refreshKey])

  // Never show figures from another range or a failed request
  const loading = overview.loading
  const failed = Boolean(overview.error) && !loading
  const data = !loading && !failed ? (overview.data ?? {}) : null
  const insights = data?.insights ?? {}

  const summary = data?.shipment_summary ?? {}
  const shipmentStatus = SHIPMENT_STATUS.map((s) => ({ name: s.label, value: Number(summary[s.key]) || 0 }))
  const shipmentTotal = shipmentStatus.reduce((sum, s) => sum + s.value, 0)
  const statusColors = Object.fromEntries(SHIPMENT_STATUS.map((s) => [s.label, s.color]))

  const refresh = () => setRefreshKey((k) => k + 1)

  const createPO = async (values) => {
    const po = await supplyChainApi.createPurchaseOrder(values)
    toast.success(po?.po_number ? `Purchase order ${po.po_number} raised` : 'Purchase order raised')
    refresh()
  }

  const actions = [
    ...(canManage ? [{ label: 'New Purchase Order', icon: Plus, tone: 'blue', onClick: () => setModal('po') }] : []),
    { label: 'Track Shipments', icon: Truck, tone: 'green', onClick: () => setModal('shipments') },
    { label: 'Manage Suppliers', icon: Users, tone: 'purple', onClick: () => setModal('suppliers') },
  ]

  const skeleton = <div className="skeleton skeleton--chart-inner" aria-label="Loading" />

  return (
    <div className="page">
      <title>Supply Chain | HIPA MASALA</title>
      <PageHeader icon={Truck} title="Supply Chain" subtitle="From farm to table. Faster, smarter, stronger.">
        <DateRangeSelect value={range} onChange={setRange} />
        {canManage && (
          <Button icon={Plus} onClick={() => setModal('po')}>
            New Purchase Order
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
                  goodWhenDown={k.goodWhenDown}
                />
              )
            })}
          </div>

          <Card title="Supply Chain Flow">{loading ? <div className="skeleton skeleton--list" aria-label="Loading" /> : <SupplyFlow steps={data?.flow} />}</Card>

          <div className="dash-row">
            <Card title="Shipment Status" subtitle="Current shipments" onViewAll={() => setModal('shipments')}>
              {loading ? (
                skeleton
              ) : (
                <DonutChart
                  data={shipmentStatus}
                  colors={statusColors}
                  valueFormatter={(v) => formatNumber(v)}
                  centerValue={formatNumber(shipmentTotal)}
                  centerLabel="Shipments"
                  size={170}
                  emptyTitle="No shipments yet"
                  emptyMessage="In-transit, delivered and delayed shipments will be counted here."
                />
              )}
            </Card>
            <Card
              title="Supplier Performance"
              subtitle="Scores in %"
              className="dash-row__wide"
              action={<MiniSelect label="Supplier performance period" value={months} onChange={setMonths} options={PERFORMANCE_MONTHS} />}
            >
              {performance.loading ? (
                skeleton
              ) : performance.error ? (
                <ErrorMessage message={performance.error.message} onRetry={performance.reload} />
              ) : (
                <SeriesChart
                  data={list(performance.data)}
                  xKey="supplier"
                  showLegend
                  xInterval={0}
                  series={[
                    { key: 'quality_pct', name: 'Quality', color: CHART_COLORS[0], type: 'bar' },
                    { key: 'on_time_pct', name: 'On-Time Delivery', color: CHART_COLORS[1], type: 'bar' },
                    { key: 'cost_efficiency_pct', name: 'Cost Efficiency', color: CHART_COLORS[2], type: 'bar' },
                  ]}
                  yFormatter={(v) => `${v}%`}
                  height={250}
                  emptyTitle="No supplier scores yet"
                  emptyMessage="Quality, on-time and cost scores appear once deliveries are recorded."
                />
              )}
            </Card>
          </div>

          <div className="dash-row">
            <Card title="Key Raw Materials" bodyClassName="card__body--flush" className="dash-row__wide">
              <Table
                compact
                loading={loading}
                caption="Key raw materials"
                data={list(data?.raw_materials)}
                emptyTitle="No raw materials tracked yet"
                emptyMessage="Stock and usage of key raw materials will appear here."
                columns={[
                  { key: 'material', header: 'Material', render: (r) => <strong>{r.material}</strong> },
                  { key: 'stock_kg', header: 'Stock', align: 'right', render: (r) => (has(r.stock_kg) ? formatKg(r.stock_kg) : '—') },
                  { key: 'monthly_usage_kg', header: 'Monthly Usage', align: 'right', render: (r) => (has(r.monthly_usage_kg) ? formatKg(r.monthly_usage_kg) : '—') },
                  { key: 'days_left', header: 'Days Left', align: 'right', render: (r) => (has(r.days_left) ? `${formatNumber(r.days_left)} days` : '—') },
                  { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
                ]}
              />
            </Card>
            <Card title="Recent Shipments" onViewAll={() => setModal('shipments')} bodyClassName="card__body--flush" className="dash-row__wide">
              <Table
                compact
                loading={loading}
                caption="Recent shipments"
                data={list(data?.recent_shipments)}
                columns={SHIPMENT_COLUMNS}
                emptyIcon={Truck}
                emptyTitle="No recent shipments"
                emptyMessage="Shipments from suppliers will appear here."
              />
            </Card>
          </div>

          <div className="dash-row">
            <Card title="Alerts & Notifications">{loading ? <div className="skeleton skeleton--list" aria-label="Loading" /> : <AlertFeed items={data?.alerts} />}</Card>
            <div className="stack">
              <InsightPanel
                title="AI Supply Chain Insight"
                text={loading ? undefined : insights.text}
                emptyText={loading ? 'Loading insights…' : undefined}
              />
              <ActionsPanel items={loading ? undefined : list(insights.actions)} emptyText={loading ? 'Loading…' : undefined} />
            </div>
            <Card title="Quick Actions">
              <QuickActions actions={actions} columns={1} />
            </Card>
          </div>
        </>
      )}

      <PurchaseOrderModal open={modal === 'po'} options={options} onClose={() => setModal(null)} onCreate={createPO} />
      <ShipmentsModal open={modal === 'shipments'} statuses={options.data?.shipment_statuses} onClose={() => setModal(null)} />
      <SuppliersModal open={modal === 'suppliers'} canManage={canManage} onClose={() => setModal(null)} onChanged={refresh} />
    </div>
  )
}
