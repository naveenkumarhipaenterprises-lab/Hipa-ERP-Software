import { CircleCheck, Clock, IndianRupee, Leaf, PackageCheck, ShoppingCart, Undo2, Users, Wallet } from 'lucide-react'
import { useState } from 'react'
import { purchaseApi } from '../../../api/purchaseApi'
import SeriesChart from '../../../components/charts/SeriesChart'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'
import { MiniSelect } from '../../../components/common/DateRangeSelect'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Table from '../../../components/common/Table'
import { ActionsPanel, InsightPanel } from '../../../components/dashboard/InsightPanel'
import StatCard from '../../../components/dashboard/StatCard'
import { useApi } from '../../../hooks/useApi'
import { CHART_COLORS } from '../../../utils/constants'
import { formatINR, formatINRShort, formatNumber } from '../../../utils/formatters'
import { has, list, money, pct, qty } from '../shared'
import { PURCHASE_COLUMNS } from './purchaseColumns'

const KPIS = [
  { key: 'total_purchases', label: 'Total Purchases', icon: ShoppingCart, tone: 'blue', format: formatNumber },
  { key: 'purchase_value', label: 'Purchase Value', icon: IndianRupee, tone: 'orange', format: formatINR, goodWhenDown: true },
  { key: 'pending_purchases', label: 'Pending Purchases', icon: Clock, tone: 'yellow', format: formatNumber, sub: 'Awaiting goods receipt' },
  { key: 'received_purchases', label: 'Received Purchases', icon: PackageCheck, tone: 'green', format: formatNumber },
  { key: 'purchase_returns', label: 'Purchase Returns', icon: Undo2, tone: 'red', format: formatNumber, goodWhenDown: true },
  { key: 'supplier_count', label: 'Active Suppliers', icon: Users, tone: 'purple', format: formatNumber },
  { key: 'outstanding_payments', label: 'Outstanding Supplier Payments', icon: Wallet, tone: 'teal', format: formatINR, sub: 'Still to be paid' },
]
const GRANULARITY = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
]

export default function PurchaseOverview({ range, rangeLabel, refreshKey }) {
  const [granularity, setGranularity] = useState('daily')
  const overview = useApi(() => purchaseApi.getOverview({ range }), [range, refreshKey])
  const trend = useApi(() => purchaseApi.getTrend({ range, granularity }), [range, granularity, refreshKey])

  const loading = overview.loading
  const failed = Boolean(overview.error) && !loading
  const data = !loading && !failed ? (overview.data ?? {}) : null
  const insights = data?.insights ?? {}

  if (failed) return <ErrorMessage message={overview.error.message} onRetry={overview.reload} />

  return (
    <>
      <div className="kpi-grid kpi-grid--auto">
        {KPIS.map((k) => {
          const kpi = data?.kpis?.[k.key]
          return (
            <StatCard key={k.key} icon={k.icon} tone={k.tone} label={k.label} loading={loading} sub={k.sub}
                      value={has(kpi?.value) ? k.format(kpi.value) : null} change={kpi?.change} changeLabel="vs prev. period" goodWhenDown={k.goodWhenDown} />
          )
        })}
      </div>

      <div className="dash-row">
        <Card title="Purchase Trend" subtitle={rangeLabel} className="dash-row__wide"
              action={<MiniSelect label="Trend granularity" value={granularity} onChange={setGranularity} options={GRANULARITY} />}>
          {trend.loading ? (
            <div className="skeleton skeleton--chart-inner" aria-label="Loading" />
          ) : trend.error ? (
            <ErrorMessage message={trend.error.message} onRetry={trend.reload} />
          ) : (
            <SeriesChart data={list(trend.data)} xKey="label" series={[{ key: 'value', name: 'Purchases', color: CHART_COLORS[1], type: 'bar' }]}
                         yFormatter={formatINRShort} tooltipFormatter={formatINR} height={260}
                         emptyTitle="No purchases in this period" emptyMessage="The trend appears once purchases are recorded." />
          )}
        </Card>
        <Card title="Top Purchased Materials" subtitle={rangeLabel} bodyClassName="card__body--flush">
          <Table compact loading={loading} caption="Top purchased materials" data={list(data?.top_materials)} rowKey={(r, i) => `${r.item}-${i}`}
                 emptyIcon={Leaf} emptyTitle="Nothing purchased yet" emptyMessage="Your most-bought items by value will appear here."
                 columns={[
                   { key: 'item', header: 'Item', render: (r) => <strong>{r.item}</strong> },
                   { key: 'quantity', header: 'Quantity', align: 'right', render: (r) => qty(r.quantity, r.unit) },
                   { key: 'value', header: 'Value', align: 'right', render: (r) => money(r.value) },
                 ]} />
        </Card>
      </div>

      <div className="dash-row">
        <Card title="Supplier Performance" subtitle="Last 6 months" bodyClassName="card__body--flush" className="dash-row__wide">
          <Table compact loading={loading} caption="Supplier performance" data={list(data?.supplier_performance)} rowKey="supplier_id"
                 emptyIcon={Users} emptyTitle="No supplier history yet" emptyMessage="On-time receipt and accepted quantity appear once goods are received."
                 columns={[
                   { key: 'supplier', header: 'Supplier', render: (r) => <strong>{r.supplier}</strong> },
                   { key: 'purchases', header: 'Purchases', align: 'right', render: (r) => formatNumber(r.purchases) },
                   { key: 'purchase_value', header: 'Value', align: 'right', render: (r) => money(r.purchase_value) },
                   { key: 'on_time_pct', header: 'On-time Receipt', align: 'right', render: (r) => pct(r.on_time_pct) },
                   { key: 'accepted_pct', header: 'Accepted', align: 'right', render: (r) => pct(r.accepted_pct) },
                   { key: 'damaged_pct', header: 'Damaged', align: 'right', render: (r) => pct(r.damaged_pct) },
                 ]} />
        </Card>
        <Card title="Low Stock Purchase Alerts" subtitle="Raw materials at or below their reorder level" bodyClassName="card__body--flush">
          <Table compact loading={loading} caption="Low stock raw materials" data={list(data?.low_stock)}
                 emptyIcon={CircleCheck} emptyTitle="No low-stock materials" emptyMessage="Materials that reach their reorder level will be listed here."
                 columns={[
                   { key: 'material', header: 'Material', render: (r) => <strong>{r.material}</strong> },
                   { key: 'current_stock', header: 'Stock', align: 'right', render: (r) => qty(r.current_stock, r.unit) },
                   { key: 'reorder_level', header: 'Reorder at', align: 'right', render: (r) => qty(r.reorder_level, r.unit) },
                   { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
                 ]} />
        </Card>
      </div>

      <Card title="Recent Purchases" bodyClassName="card__body--flush">
        <Table compact loading={loading} caption="Recent purchases" data={list(data?.recent_purchases)} columns={PURCHASE_COLUMNS}
               emptyIcon={ShoppingCart} emptyTitle="No purchases yet" emptyMessage="Recorded purchases will appear here." />
      </Card>

      <div className="grid-2">
        <InsightPanel title="AI Purchase Insight" text={loading ? undefined : insights.text} emptyText={loading ? 'Loading insights…' : undefined} />
        <ActionsPanel title="Suggested Purchases" items={loading ? undefined : list(insights.actions)} emptyText={loading ? 'Loading…' : undefined} />
      </div>
    </>
  )
}
