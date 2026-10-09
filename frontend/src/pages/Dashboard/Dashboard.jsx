import {
  BarChart3,
  Bot,
  FileText,
  House,
  Megaphone,
  Package,
  PackageCheck,
  RefreshCw,
  ShoppingBag,
  ShoppingCart,
  Truck,
  UserPlus,
  Users,
  Wallet,
} from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { dashboardApi } from '../../api/dashboardApi'
import DonutChart from '../../components/charts/DonutChart'
import SeriesChart from '../../components/charts/SeriesChart'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import DateRangeSelect, { MiniSelect } from '../../components/common/DateRangeSelect'
import ErrorMessage from '../../components/common/ErrorMessage'
import PageHeader from '../../components/common/PageHeader'
import Table from '../../components/common/Table'
import QuickActions from '../../components/dashboard/QuickActions'
import StatCard from '../../components/dashboard/StatCard'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import BrandBanner from '../../modules/dashboard/components/BrandBanner'
import OrderStatusList from '../../modules/dashboard/components/OrderStatusList'
import PurchaseSection from '../../modules/dashboard/components/PurchaseSection'
import UpcomingActivities from '../../modules/dashboard/components/UpcomingActivities'
import { DATE_RANGES, hasAnyRole } from '../../utils/constants'
import { formatINR, formatINRShort, formatKg, formatNumber, formatPercent } from '../../utils/formatters'

const TREND_PERIODS = [
  { value: 'last_12_months', label: 'Last 12 Months' },
  { value: 'last_6_months', label: 'Last 6 Months' },
]

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''

/** KPI cards: which module each needs, and how its value is formatted. */
const KPIS = [
  { key: 'total_sales', label: 'Total Sales', icon: ShoppingCart, tone: 'green', module: 'sales', format: formatINR },
  { key: 'total_orders', label: 'Total Orders', icon: Package, tone: 'blue', module: 'sales', format: formatNumber },
  { key: 'total_customers', label: 'Total Customers', icon: Users, tone: 'orange', module: 'customers', format: formatNumber },
  { key: 'active_suppliers', label: 'Active Suppliers', icon: Truck, tone: 'red', module: 'purchase', format: formatNumber },
  { key: 'purchase_value', label: 'Purchase Value', icon: ShoppingBag, tone: 'teal', module: 'purchase', format: formatINR },
  { key: 'outstanding_supplier_payments', label: 'Supplier Payments Due', icon: Wallet, tone: 'yellow', module: 'purchase', format: formatINR },
]

// `roles`: who may create that record (the backend refuses everyone else), so others don't get a dead button
const SALES_MANAGERS = ['admin', 'management', 'sales']
const QUICK_ACTIONS = [
  { label: 'New Order', icon: ShoppingCart, tone: 'green', to: '/sales?new=order', module: 'sales', roles: SALES_MANAGERS },
  { label: 'New Quotation', icon: FileText, tone: 'teal', to: '/sales?tab=quotations', module: 'sales', roles: SALES_MANAGERS },
  { label: 'Record Purchase', icon: ShoppingBag, tone: 'orange', to: '/purchase?tab=purchases', module: 'purchase', roles: ['admin', 'management', 'purchase'] },
  { label: 'Add Customer', icon: UserPlus, tone: 'blue', to: '/customers?new=customer', module: 'customers', roles: SALES_MANAGERS },
  { label: 'Update Inventory', icon: Package, tone: 'orange', to: '/inventory', module: 'inventory', roles: ['admin', 'management', 'inventory'] },
  { label: 'Create Campaign', icon: Megaphone, tone: 'red', to: '/marketing?new=campaign', module: 'marketing', roles: ['admin', 'management', 'marketing'] },
  { label: 'Generate Report', icon: BarChart3, tone: 'blue', to: '/reports', module: 'reports' },
  { label: 'AI Assistant', icon: Bot, tone: 'purple', to: '/ai-assistant', module: 'aiAssistant' },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const { user, can } = useAuth()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [period, setPeriod] = useState(TREND_PERIODS[0].value)

  const summary = useApi(() => dashboardApi.getSummary(range), [range])
  const canSales = can('sales')
  const trend = useApi(() => (canSales ? dashboardApi.getSalesTrend(period) : Promise.resolve([])), [period, canSales])

  // Never show numbers from a different range or a failed request
  const loading = summary.loading
  const failed = Boolean(summary.error) && !loading
  const data = !loading && !failed ? (summary.data ?? {}) : null

  const rangeLabel = DATE_RANGES.find((r) => r.value === range)?.label ?? ''
  const kpis = KPIS.filter((k) => can(k.module))
  const firstName = (user?.name || user?.username || '').split(' ')[0]
  const actions = QUICK_ACTIONS.filter((a) => can(a.module) && (!a.roles || hasAnyRole(user, a.roles))).map((a) => ({ ...a, onClick: () => navigate(a.to) }))

  const contribution = list(data?.product_contribution).map((p) => ({ name: p.name, value: Number(p.value) || 0 }))
  const contributionTotal = contribution.reduce((s, p) => s + p.value, 0)

  const reload = () => {
    summary.reload()
    trend.reload()
  }

  return (
    <div className="page">
      <title>Dashboard | HIPA MASALA</title>
      <PageHeader
        icon={House}
        title="Dashboard"
        subtitle={`Welcome back${firstName ? `, ${firstName}` : ''}! Here's what's happening at HIPA MASALA.`}
      >
        <DateRangeSelect value={range} onChange={setRange} />
        <Button variant="outline" icon={RefreshCw} onClick={reload} loading={loading}>
          Refresh
        </Button>
      </PageHeader>

      {failed && <ErrorMessage message={summary.error.message} onRetry={reload} />}

      {kpis.length > 0 && !failed && (
        <div className="kpi-grid kpi-grid--auto">
          {kpis.map((k) => {
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
              />
            )
          })}
        </div>
      )}

      {/* One page-level banner is enough when the summary fails; the chart's own error only shows alone */}
      {canSales && !failed && (
        <div className="dash-row">
          <Card
            title="Sales Overview"
            className="dash-row__wide"
            action={<MiniSelect label="Sales overview period" value={period} onChange={setPeriod} options={TREND_PERIODS} />}
          >
            {trend.loading ? (
              <div className="skeleton skeleton--chart-inner" aria-label="Loading" />
            ) : trend.error ? (
              <ErrorMessage message={trend.error.message} onRetry={trend.reload} />
            ) : (
              <SeriesChart
                data={list(trend.data)}
                xKey="label"
                series={[{ key: 'sales', name: 'Sales', color: 'var(--green-600)', type: 'area', dots: true }]}
                yFormatter={formatINRShort}
                tooltipFormatter={(v) => formatINR(v)}
                height={260}
                emptyTitle="No sales recorded"
                emptyMessage="Monthly sales will appear here once orders are recorded."
              />
            )}
          </Card>

          <Card title="Product Sales Contribution" subtitle={rangeLabel}>
            {loading ? (
              <div className="skeleton skeleton--chart-inner" aria-label="Loading" />
            ) : (
              <DonutChart
                data={contribution}
                valueFormatter={(v) => formatINR(v)}
                legendValue={(d) => formatPercent((d.value / contributionTotal) * 100, 1)}
                centerValue={formatINRShort(contributionTotal)}
                centerLabel="Total Sales"
                size={180}
                emptyTitle="No product sales"
                emptyMessage="Sales by product will appear here."
              />
            )}
          </Card>

          <Card title="Order Status" subtitle={rangeLabel} viewAllTo="/sales">
            {loading ? <div className="skeleton skeleton--chart-inner" aria-label="Loading" /> : <OrderStatusList items={data?.order_status} />}
          </Card>
        </div>
      )}

      {can('purchase') && !failed && <PurchaseSection loading={loading} data={data} rangeLabel={rangeLabel} />}

      {!failed && (canSales || can('inventory') || can('customers')) && (
        <div className="dash-row">
          {canSales && (
            <Card title="Recent Orders" viewAllTo="/sales" className="dash-row__wide" bodyClassName="card__body--flush">
              <Table
                compact
                loading={loading}
                caption="Recent orders"
                data={list(data?.recent_orders)}
                emptyIcon={ShoppingCart}
                emptyTitle="No recent orders"
                emptyMessage="New orders will appear here."
                columns={[
                  { key: 'order_number', header: 'Order ID', render: (r) => r.order_number || '—' },
                  { key: 'customer', header: 'Customer' },
                  { key: 'product', header: 'Product' },
                  { key: 'amount', header: 'Amount', align: 'right', render: (r) => (has(r.amount) ? formatINR(r.amount) : '—') },
                  { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
                ]}
              />
            </Card>
          )}

          {can('inventory') && (
            <Card title="Low Stock Alerts" viewAllTo="/inventory" bodyClassName="card__body--flush">
              <Table
                compact
                loading={loading}
                caption="Low stock alerts"
                data={list(data?.low_stock)}
                emptyIcon={PackageCheck}
                emptyTitle="No low stock alerts"
                emptyMessage="Products below their reorder level will appear here."
                columns={[
                  { key: 'product', header: 'Product' },
                  { key: 'stock_kg', header: 'Stock', align: 'right', render: (r) => (has(r.stock_kg) ? formatKg(r.stock_kg) : '—') },
                  { key: 'reorder_level_kg', header: 'Reorder At', align: 'right', render: (r) => (has(r.reorder_level_kg) ? formatKg(r.reorder_level_kg) : '—') },
                  { key: 'status', header: 'Status', render: (r) => <Badge>{r.status || 'Low Stock'}</Badge> },
                ]}
              />
            </Card>
          )}

          {can('customers') && (
            <Card title="Top Customers" subtitle={rangeLabel} viewAllTo="/customers" bodyClassName="card__body--flush">
              <Table
                compact
                numbered
                loading={loading}
                caption="Top customers"
                data={list(data?.top_customers)}
                emptyIcon={Users}
                emptyTitle="No customer sales yet"
                emptyMessage="Your highest-value customers will appear here."
                columns={[
                  { key: 'name', header: 'Customer' },
                  { key: 'amount', header: 'Sales', align: 'right', render: (r) => (has(r.amount) ? formatINR(r.amount) : '—') },
                ]}
              />
            </Card>
          )}
        </div>
      )}

      <div className="dash-row">
        {actions.length > 0 && (
          <Card title="Quick Actions">
            <QuickActions actions={actions} columns={2} />
          </Card>
        )}
        {!failed && (
          <Card title="Upcoming Activities" subtitle="Next 7 days">
            {loading ? <div className="skeleton skeleton--list" aria-label="Loading" /> : <UpcomingActivities items={data?.upcoming} />}
          </Card>
        )}
        <BrandBanner />
      </div>
    </div>
  )
}
