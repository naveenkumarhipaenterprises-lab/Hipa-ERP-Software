import { CircleCheck, Sparkles, Users } from 'lucide-react'
import SeriesChart from '../../../components/charts/SeriesChart'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'
import EmptyState from '../../../components/common/EmptyState'
import Table from '../../../components/common/Table'
import { CHART_COLORS } from '../../../utils/constants'
import { list, money, pct, qty } from '../../../utils/display'
import { formatINR, formatINRShort, formatNumber } from '../../../utils/formatters'

const skeleton = <div className="skeleton skeleton--chart-inner" aria-label="Loading" />

/**
 * Dashboard purchase widgets (GET /dashboard/summary/ for roles that can open Purchase):
 * overview, 6-month trend, AI purchase recommendations, supplier performance and low-stock purchase alerts.
 */
export default function PurchaseSection({ loading, data, rangeLabel }) {
  const overview = data?.purchase_overview ?? {}
  const recs = list(data?.purchase_recommendations)
  return (
    <>
      <div className="dash-row">
        <Card title="Purchase Overview" subtitle={rangeLabel} viewAllTo="/purchase">
          {loading ? (
            <div className="skeleton skeleton--list" aria-label="Loading" />
          ) : (
            <dl className="detail-grid">
              {[['Purchases', overview.purchases], ['Awaiting receipt', overview.pending], ['Received', overview.received], ['Returns', overview.returns]].map(
                ([label, v]) => (
                  <div key={label}><dt>{label}</dt><dd>{v === undefined ? '—' : formatNumber(v)}</dd></div>
                ),
              )}
            </dl>
          )}
        </Card>
        <Card title="Purchase Trend" subtitle="Last 6 months" className="dash-row__wide">
          {loading ? skeleton : (
            <SeriesChart data={list(data?.purchase_trend)} xKey="label" series={[{ key: 'value', name: 'Purchases', color: CHART_COLORS[1], type: 'bar' }]}
                         yFormatter={formatINRShort} tooltipFormatter={formatINR} height={220}
                         emptyTitle="No purchases recorded" emptyMessage="Monthly purchase value appears once purchases are recorded." />
          )}
        </Card>
        <Card title="AI Purchase Recommendations" viewAllTo="/purchase?tab=recommendations">
          {loading ? (
            <div className="skeleton skeleton--list" aria-label="Loading" />
          ) : recs.length === 0 ? (
            <EmptyState compact icon={Sparkles} title="No purchase recommendations"
                        message="The daily analysis lists items to buy once usage, sales and stock data are available." />
          ) : (
            <ul className="stack" style={{ margin: 0, padding: 0, listStyle: 'none' }}>
              {recs.map((r) => (
                <li key={r.id}>
                  <strong>{r.title}</strong> {r.priority && <Badge>{r.priority}</Badge>}
                  <p className="muted" style={{ margin: '2px 0 0' }}>{r.action || r.text}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="dash-row">
        <Card title="Supplier Performance" subtitle="Last 6 months" viewAllTo="/purchase" className="dash-row__wide" bodyClassName="card__body--flush">
          <Table compact loading={loading} caption="Supplier performance" data={list(data?.supplier_performance)} rowKey="supplier_id"
                 emptyIcon={Users} emptyTitle="No supplier history yet" emptyMessage="On-time receipt and accepted quantities appear once goods are received."
                 columns={[
                   { key: 'supplier', header: 'Supplier' },
                   { key: 'purchase_value', header: 'Purchases', align: 'right', render: (r) => money(r.purchase_value) },
                   { key: 'on_time_pct', header: 'On-time', align: 'right', render: (r) => pct(r.on_time_pct) },
                   { key: 'accepted_pct', header: 'Accepted', align: 'right', render: (r) => pct(r.accepted_pct) },
                 ]} />
        </Card>
        <Card title="Low Stock Purchase Alerts" subtitle="Raw materials at or below reorder level" viewAllTo="/purchase?tab=materials" bodyClassName="card__body--flush">
          <Table compact loading={loading} caption="Low stock raw materials" data={list(data?.low_stock_materials)}
                 emptyIcon={CircleCheck} emptyTitle="No purchase risks" emptyMessage="Raw materials that reach their reorder level appear here."
                 columns={[
                   { key: 'material', header: 'Material' },
                   { key: 'current_stock', header: 'Stock', align: 'right', render: (r) => qty(r.current_stock, r.unit) },
                   { key: 'reorder_level', header: 'Reorder At', align: 'right', render: (r) => qty(r.reorder_level, r.unit) },
                   { key: 'status', header: 'Status', render: (r) => <Badge>{r.status}</Badge> },
                 ]} />
        </Card>
      </div>
    </>
  )
}
