import { CalendarDays, ChartNoAxesColumnIncreasing, CircleCheck, Download, IndianRupee, RefreshCw, Sparkles, TrendingUp } from 'lucide-react'
import { useState } from 'react'
import { purchaseApi } from '../../../api/purchaseApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import DateRangeSelect from '../../../components/common/DateRangeSelect'
import EmptyState from '../../../components/common/EmptyState'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Table from '../../../components/common/Table'
import StatCard from '../../../components/dashboard/StatCard'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatINR, formatNumber } from '../../../utils/formatters'
import { dash, has, list, money, qty } from '../shared'

const HORIZONS = [
  { value: '30', label: 'Next 30 Days' },
  { value: '15', label: 'Next 15 Days' },
  { value: '7', label: 'Next 7 Days' },
]
const PRIORITY_PILL = { HIGH: 'cell-pill--red', MEDIUM: 'cell-pill--amber', LOW: 'cell-pill--green' }
const INSUFFICIENT = 'Insufficient data for AI recommendation.'

/**
 * AI purchase recommendations from the backend (usage, sales forecast, stock, reorder levels, safety stock,
 * on-order quantities, measured supplier lead times and price history). Nothing is calculated here.
 */
export default function RecommendationsPanel({ canManage, onBuy }) {
  const toast = useToast()
  const [horizon, setHorizon] = useState('30')
  const [exporting, setExporting] = useState(false)
  const rec = useApi(() => purchaseApi.getRecommendations({ horizon }), [horizon])

  const loading = rec.loading
  const failed = Boolean(rec.error) && !loading
  const data = !loading && !failed ? (rec.data ?? {}) : null
  const rows = list(data?.rows)
  const summary = data?.summary ?? {}

  const exportCsv = async () => {
    setExporting(true)
    try {
      await purchaseApi.exportRecommendations({ horizon })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setExporting(false)
    }
  }

  const columns = [
    { key: 'item', header: 'Item', render: (r) => (
      <span>
        <strong>{r.item}</strong>
        <span className="muted"> · {r.item_type === 'material' ? 'Raw material' : 'Product'}</span>
        {list(r.notes).length > 0 && <ul className="list-notes">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      </span>
    ) },
    { key: 'priority', header: 'Priority', align: 'center', render: (r) => <Badge>{r.priority}</Badge> },
    { key: 'current_stock', header: 'Stock', align: 'right', render: (r) => qty(r.current_stock, r.unit) },
    { key: 'on_order', header: 'On Order', align: 'right', render: (r) => qty(r.on_order, r.unit) },
    { key: 'avg_daily_demand', header: 'Daily Demand', align: 'right', render: (r) => qty(r.avg_daily_demand, r.unit) },
    { key: 'lead_time_days', header: 'Lead Time', align: 'right', render: (r) => (has(r.lead_time_days) ? `${formatNumber(r.lead_time_days)} days` : '—') },
    { key: 'safety_stock', header: 'Safety Stock', align: 'right', render: (r) => qty(r.safety_stock, r.unit) },
    { key: 'days_of_cover', header: 'Days of Cover', align: 'right', render: (r) => (has(r.days_of_cover) ? formatNumber(r.days_of_cover) : '—') },
    { key: 'recommended_quantity', header: 'Recommended', align: 'center',
      render: (r) => <span className={`cell-pill ${PRIORITY_PILL[r.priority] ?? ''}`}>{qty(r.recommended_quantity, r.unit)}</span> },
    { key: 'last_price', header: 'Last Price', align: 'right', render: (r) => (
      <span className="nowrap">
        {money(r.last_price)}
        {has(r.price_change_pct) && r.price_change_pct !== 0 && (
          <span className={r.price_change_pct > 0 ? 'text-red' : 'text-green'}> ({r.price_change_pct > 0 ? '+' : ''}{r.price_change_pct}%)</span>
        )}
      </span>
    ) },
    { key: 'estimated_cost', header: 'Est. Cost', align: 'right', render: (r) => money(r.estimated_cost) },
    { key: 'best_supplier', header: 'Best Price From', render: (r) => dash(r.best_supplier ?? r.preferred_supplier) },
  ]
  if (canManage) {
    columns.push({
      key: 'buy', sticky: true, header: <span className="sr-only">Actions</span>, align: 'center',
      render: (r) => Number(r.recommended_quantity) > 0 && (
        <Button size="sm" onClick={() => onBuy(r)} aria-label={`Record a purchase of ${r.item}`}>Buy</Button>
      ),
    })
  }

  return (
    <>
      <div className="toolbar toolbar--plain">
        <DateRangeSelect value={horizon} onChange={setHorizon} options={HORIZONS} />
        <Button variant="outline" icon={RefreshCw} onClick={rec.reload} loading={loading}>Refresh</Button>
        <Button icon={Download} onClick={exportCsv} loading={exporting} disabled={rows.length === 0}>Export CSV</Button>
      </div>

      {failed ? (
        <ErrorMessage message={rec.error.message} onRetry={rec.reload} />
      ) : (
        <>
          <div className="kpi-grid kpi-grid--auto">
            <StatCard icon={TrendingUp} tone="red" valueTone="red" label="High Priority" sub="Buy now" loading={loading} value={data?.status === 'ok' ? formatNumber(summary.high) : null} emptyText={INSUFFICIENT} />
            <StatCard icon={ChartNoAxesColumnIncreasing} tone="orange" valueTone="orange" label="Medium Priority" sub="Buy within the period" loading={loading} value={data?.status === 'ok' ? formatNumber(summary.medium) : null} emptyText={INSUFFICIENT} />
            <StatCard icon={CircleCheck} tone="green" valueTone="green" label="Sufficient Stock" sub="No purchase needed" loading={loading} value={data?.status === 'ok' ? formatNumber(summary.low) : null} emptyText={INSUFFICIENT} />
            <StatCard icon={IndianRupee} tone="blue" label="Estimated Cost" sub="At last purchase prices" loading={loading} value={has(summary.estimated_cost) ? formatINR(summary.estimated_cost) : null} emptyText="—" />
          </div>

          <Card
            title="AI Purchase Recommendations"
            subtitle={`Period: ${HORIZONS.find((h) => h.value === horizon)?.label}`}
            bodyClassName="card__body--flush"
            action={data?.generated_at && (
              <span className="plan-meta">
                <span className="chip chip--green"><Sparkles size={14} aria-hidden /> From your data</span>
                <span className="muted"><CalendarDays size={15} aria-hidden /> {formatDate(data.generated_at)}</span>
              </span>
            )}
          >
            <Table numbered loading={loading} caption="AI purchase recommendations" data={rows} rowKey={(r) => `${r.item_type}-${r.item_id}`} columns={columns}
                   emptyIcon={Sparkles} emptyTitle={INSUFFICIENT}
                   emptyMessage="Recommendations need recorded raw-material usage (14+ days) or 4+ weeks of sales, plus your stock levels. Record usage under Raw Materials." />
          </Card>

          {list(data?.insufficient).length > 0 && (
            <Card title="Not enough data yet" subtitle="These items were skipped instead of guessed" bodyClassName="card__body--flush">
              <Table compact caption="Items without enough data" data={data.insufficient} rowKey={(r, i) => `${r.item}-${i}`}
                     columns={[{ key: 'item', header: 'Item', render: (r) => <strong>{r.item}</strong> },
                               { key: 'item_type', header: 'Type', render: (r) => (r.item_type === 'material' ? 'Raw material' : 'Product') },
                               { key: 'reason', header: 'What is missing' }]} />
            </Card>
          )}
          {!loading && data?.status !== 'ok' && list(data?.insufficient).length === 0 && (
            <EmptyState compact title={INSUFFICIENT} message="Add raw materials and products, then record purchases, goods receipts and usage." />
          )}
        </>
      )}
    </>
  )
}
