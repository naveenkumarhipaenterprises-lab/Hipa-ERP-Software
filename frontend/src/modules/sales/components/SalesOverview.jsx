import { Download, IndianRupee, Package, ShoppingBag, Users } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { salesApi } from '../../../api/salesApi'
import DonutChart from '../../../components/charts/DonutChart'
import SeriesChart from '../../../components/charts/SeriesChart'
import Sparkline from '../../../components/charts/Sparkline'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import { MiniSelect } from '../../../components/common/DateRangeSelect'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Table from '../../../components/common/Table'
import { InsightPanel } from '../../../components/dashboard/InsightPanel'
import StatCard from '../../../components/dashboard/StatCard'
import { useApi } from '../../../hooks/useApi'
import { useAuth } from '../../../hooks/useAuth'
import { downloadCSV } from '../../../utils/exporters'
import { formatINR, formatINRShort, formatKg, formatNumber, formatPercent } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''
const num = (v) => Number(v) || 0

const KPIS = [
  { key: 'total_sales', label: 'Total Sales', icon: IndianRupee, tone: 'green', format: formatINR },
  { key: 'total_orders', label: 'Total Orders', icon: ShoppingBag, tone: 'blue', format: formatNumber },
  { key: 'quantity_sold_kg', label: 'Total Quantity Sold', icon: Package, tone: 'purple', format: formatKg },
  { key: 'new_customers', label: 'New Customers', icon: Users, tone: 'orange', format: formatNumber },
]

const GRANULARITY = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
]

function Growth({ value }) {
  if (!has(value) || !Number.isFinite(Number(value))) return <span className="muted">—</span>
  const n = Number(value)
  return (
    <span className={`strong ${n >= 0 ? 'text-up' : 'text-down'}`}>
      {n >= 0 ? '↑' : '↓'} {formatPercent(Math.abs(n), 1)}
    </span>
  )
}

const withShare = (items) => {
  const rows = list(items).map((d) => ({ name: d.name, value: num(d.value) }))
  const total = rows.reduce((s, d) => s + d.value, 0)
  return { rows, total, share: (d) => (total ? formatPercent((d.value / total) * 100, 1) : '—') }
}

/** Sales overview tab: KPIs, trend, product and customer-type split, product table, top customers. */
export default function SalesOverview({ range, product, rangeLabel, refreshKey }) {
  const { can } = useAuth()
  const [granularity, setGranularity] = useState('daily')
  const overview = useApi(() => salesApi.getOverview({ range, product }), [range, product, refreshKey])
  const trend = useApi(() => salesApi.getTrend({ range, product, granularity }), [range, product, granularity, refreshKey])

  // Never show figures from another filter or a failed request
  const loading = overview.loading
  const failed = Boolean(overview.error) && !loading
  const data = !loading && !failed ? (overview.data ?? {}) : null

  if (failed) {
    return (
      <ErrorMessage
        message={overview.error.message}
        onRetry={() => {
          overview.reload()
          trend.reload()
        }}
      />
    )
  }

  const products = list(data?.products)
  const productShare = withShare(data?.product_share)
  const customerTypes = withShare(data?.customer_types)

  const exportCSV = () =>
    downloadCSV(`hipa-sales-by-product-${range}.csv`, products, [
      { key: 'product', header: 'Product' },
      { key: 'quantity_kg', header: 'Quantity Sold (kg)' },
      { key: 'sales', header: 'Total Sales (INR)' },
      { key: 'orders', header: 'Orders' },
      { key: 'avg_price', header: 'Avg. Price (INR/kg)' },
      { key: 'growth', header: 'Growth %' },
    ])

  const chartSkeleton = <div className="skeleton skeleton--chart-inner" aria-label="Loading" />

  return (
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
            />
          )
        })}
      </div>

      <div className="dash-row">
        <Card
          title="Sales Trend"
          subtitle={rangeLabel}
          className="dash-row__wide"
          action={<MiniSelect label="Trend granularity" value={granularity} onChange={setGranularity} options={GRANULARITY} />}
        >
          {trend.loading ? (
            chartSkeleton
          ) : trend.error ? (
            <ErrorMessage message={trend.error.message} onRetry={trend.reload} />
          ) : (
            <SeriesChart
              data={list(trend.data)}
              xKey="label"
              series={[{ key: 'sales', name: 'Sales', color: 'var(--blue-600)', type: 'area', dots: true }]}
              yFormatter={formatINRShort}
              tooltipFormatter={(v) => formatINR(v)}
              height={250}
              emptyTitle="No sales in this period"
              emptyMessage="The trend will appear once orders are recorded."
            />
          )}
        </Card>

        <Card title="Product-wise Sales" subtitle={rangeLabel}>
          {loading ? (
            chartSkeleton
          ) : (
            <DonutChart
              data={productShare.rows}
              valueFormatter={(v) => formatINR(v)}
              legendValue={productShare.share}
              centerValue={formatINRShort(productShare.total)}
              centerLabel="Total Sales"
              size={170}
              emptyTitle="No product sales"
              emptyMessage="Sales by product will appear here."
            />
          )}
        </Card>

        <Card title="Customer Type" subtitle={rangeLabel}>
          {loading ? (
            chartSkeleton
          ) : (
            <DonutChart
              data={customerTypes.rows}
              valueFormatter={(v) => `${formatNumber(v)} orders`}
              legendValue={customerTypes.share}
              centerValue={formatNumber(customerTypes.total)}
              centerLabel="Total Orders"
              size={170}
              emptyTitle="No orders by customer type"
              emptyMessage="The split by customer type will appear here."
            />
          )}
        </Card>
      </div>

      <div className="grid-main-side">
        <Card
          title="Product Sales Details"
          subtitle={rangeLabel}
          bodyClassName="card__body--flush"
          action={
            <Button variant="outline" size="sm" icon={Download} onClick={exportCSV} disabled={loading || products.length === 0}>
              Export CSV
            </Button>
          }
        >
          <Table
            numbered
            loading={loading}
            caption="Product sales details"
            data={products}
            pageSize={10}
            emptyIcon={Package}
            emptyTitle="No product sales in this period"
            emptyMessage="Each product's sales will be listed here."
            columns={[
              { key: 'product', header: 'Product' },
              { key: 'quantity_kg', header: 'Qty Sold (kg)', align: 'right', render: (r) => (has(r.quantity_kg) ? formatNumber(r.quantity_kg) : '—') },
              { key: 'sales', header: 'Total Sales', align: 'right', render: (r) => (has(r.sales) ? formatINR(r.sales) : '—') },
              { key: 'orders', header: 'Orders', align: 'right', render: (r) => (has(r.orders) ? formatNumber(r.orders) : '—') },
              { key: 'avg_price', header: 'Avg. Price (₹/kg)', align: 'right', render: (r) => (has(r.avg_price) ? Number(r.avg_price).toFixed(2) : '—') },
              { key: 'growth', header: 'Growth', render: (r) => <Growth value={r.growth} /> },
              { key: 'trend', header: 'Trend', render: (r) => <Sparkline values={r.trend} /> },
            ]}
          />
        </Card>

        <div className="stack">
          <Card title="Top Customers" subtitle={rangeLabel} viewAllTo={can('customers') ? '/customers' : undefined} bodyClassName="card__body--flush">
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
                { key: 'type', header: 'Type', render: (r) => r.type || '—' },
                { key: 'amount', header: 'Sales', align: 'right', render: (r) => (has(r.amount) ? formatINR(r.amount) : '—') },
              ]}
            />
          </Card>
          <InsightPanel
            title="AI Sales Insight"
            items={loading ? undefined : list(data?.insights).filter((s) => typeof s === 'string' && s.trim())}
            emptyText={loading ? 'Loading insights…' : undefined}
            action={
              can('aiAssistant') && (
                <Link className="link" to="/ai-assistant?q=Summarise%20sales%20for%20this%20period">
                  Ask AI
                </Link>
              )
            }
          />
        </div>
      </div>
    </>
  )
}
