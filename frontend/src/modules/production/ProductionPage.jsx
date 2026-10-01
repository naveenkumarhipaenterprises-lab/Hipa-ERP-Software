import { CalendarDays, ChartNoAxesColumnIncreasing, CircleCheck, Download, Factory, RefreshCw, Sparkles, TrendingUp } from 'lucide-react'
import { useState } from 'react'
import { productionApi } from '../../api/productionApi'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import DateRangeSelect from '../../components/common/DateRangeSelect'
import ErrorMessage from '../../components/common/ErrorMessage'
import PageHeader from '../../components/common/PageHeader'
import Table from '../../components/common/Table'
import { ActionsPanel, InsightPanel } from '../../components/dashboard/InsightPanel'
import StatCard from '../../components/dashboard/StatCard'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { formatDate, formatNumber } from '../../utils/formatters'
import BatchesTable from './components/BatchesTable'
import ScheduleBatchModal from './components/ScheduleBatchModal'

// Roles that may schedule batches or change their stage (the backend enforces the same rule)
const PRODUCTION_MANAGERS = ['admin', 'management', 'production']

const HORIZONS = [
  { value: '30', label: 'Next 30 Days' },
  { value: '15', label: 'Next 15 Days' },
  { value: '7', label: 'Next 7 Days' },
]
const PRIORITY_PILL = { HIGH: 'cell-pill--red', MEDIUM: 'cell-pill--amber', LOW: 'cell-pill--green' }

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''
const kg = (v) => (has(v) ? formatNumber(v) : '—')

const KPIS = [
  { key: 'total_products', label: 'Total Products', icon: Factory, tone: 'blue', sub: 'In this plan' },
  { key: 'high', label: 'High Priority', icon: TrendingUp, tone: 'red', sub: 'Need immediate production', valueTone: 'red' },
  { key: 'medium', label: 'Medium Priority', icon: ChartNoAxesColumnIncreasing, tone: 'orange', sub: 'Products to monitor', valueTone: 'orange' },
  { key: 'low', label: 'Low Priority', icon: CircleCheck, tone: 'green', sub: 'Sufficient stock', valueTone: 'green' },
]

export default function ProductionPage() {
  const { user } = useAuth()
  const toast = useToast()
  const [horizon, setHorizon] = useState(HORIZONS[0].value)
  const [scheduling, setScheduling] = useState(null) // { row } | { row: null } for a blank batch
  const [refreshKey, setRefreshKey] = useState(0)
  const [exporting, setExporting] = useState(false)

  const canManage = PRODUCTION_MANAGERS.includes(user?.role)
  const plan = useApi(() => productionApi.getPlan({ horizon }), [horizon, refreshKey])
  const options = useApi(() => productionApi.getOptions(), [])

  // Never show a plan for another horizon or from a failed request
  const loading = plan.loading
  const failed = Boolean(plan.error) && !loading
  const data = !loading && !failed ? (plan.data ?? {}) : null
  const rows = list(data?.rows)
  const hasPlan = rows.length > 0
  const insights = data?.insights ?? {}
  const horizonLabel = HORIZONS.find((h) => h.value === horizon)?.label ?? ''

  const refresh = () => setRefreshKey((k) => k + 1)

  const exportPlan = async () => {
    setExporting(true)
    try {
      await productionApi.exportPlan({ horizon })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setExporting(false)
    }
  }

  const schedule = async (values) => {
    const batch = await productionApi.scheduleBatch(values)
    toast.success(batch?.batch_number ? `Batch ${batch.batch_number} scheduled` : 'Batch scheduled')
    refresh()
  }

  const columns = [
    { key: 'product', header: 'Product', render: (r) => <strong>{r.product}</strong> },
    { key: 'stock_kg', header: 'Current Stock (kg)', align: 'center', render: (r) => kg(r.stock_kg) },
    { key: 'forecast_kg', header: 'Forecast Demand (kg)', align: 'center', render: (r) => kg(r.forecast_kg) },
    { key: 'safety_stock_kg', header: 'Safety Stock (kg)', align: 'center', render: (r) => kg(r.safety_stock_kg) },
    {
      key: 'required_kg',
      header: 'Required (kg)',
      align: 'center',
      render: (r) => <span className={`cell-pill ${PRIORITY_PILL[r.priority] ?? ''}`}>{kg(r.required_kg)}</span>,
    },
    { key: 'capacity_kg', header: 'Capacity (kg)', align: 'center', render: (r) => kg(r.capacity_kg) },
    {
      key: 'recommended_kg',
      header: 'Recommended (kg)',
      align: 'center',
      render: (r) => <span className="cell-pill cell-pill--blue">{kg(r.recommended_kg)}</span>,
    },
    { key: 'priority', header: 'Priority', align: 'center', render: (r) => (r.priority ? <Badge>{r.priority}</Badge> : '—') },
  ]
  if (canManage) {
    columns.push({
      key: 'plan',
      sticky: true,
      header: <span className="sr-only">Actions</span>,
      align: 'center',
      render: (r) =>
        Number(r.recommended_kg) > 0 ? (
          <Button size="sm" onClick={() => setScheduling({ row: r })} aria-label={`Schedule a batch of ${r.product}`}>
            Plan
          </Button>
        ) : (
          <span className="muted">—</span>
        ),
    })
  }

  return (
    <div className="page">
      <title>Production | HIPA MASALA</title>
      <PageHeader
        icon={Factory}
        title="Production Plan"
        subtitle="Production recommendations based on demand forecast and inventory"
      >
        <DateRangeSelect value={horizon} onChange={setHorizon} options={HORIZONS} />
        <Button variant="outline" icon={RefreshCw} onClick={refresh} loading={loading}>
          Refresh
        </Button>
        <Button icon={Download} onClick={exportPlan} loading={exporting} disabled={!hasPlan}>
          Export Plan
        </Button>
      </PageHeader>

      {failed && <ErrorMessage message={plan.error.message} onRetry={refresh} />}

      {!failed && (
        <>
          <div className="kpi-grid">
            {KPIS.map((k) => {
              const v = data?.summary?.[k.key]
              return (
                <StatCard
                  key={k.key}
                  icon={k.icon}
                  tone={k.tone}
                  label={k.label}
                  loading={loading}
                  value={has(v) ? formatNumber(v) : null}
                  sub={k.sub}
                  valueTone={k.valueTone}
                  emptyText="No plan yet"
                />
              )
            })}
          </div>

          <Card
            title="Recommended Production Plan"
            subtitle={`Forecast period: ${horizonLabel}`}
            bodyClassName="card__body--flush"
            action={
              hasPlan &&
              data?.generated_at && (
                <span className="plan-meta">
                  <span className="chip chip--green">
                    <Sparkles size={14} aria-hidden /> Generated plan
                  </span>
                  <span className="muted">
                    <CalendarDays size={15} aria-hidden /> {formatDate(data.generated_at)}
                  </span>
                </span>
              )
            }
          >
            <Table
              numbered
              loading={loading}
              caption="Recommended production plan"
              rowKey={(r, i) => r.product_id ?? i}
              data={rows}
              columns={columns}
              emptyIcon={Sparkles}
              emptyTitle="No production plan has been generated yet"
              emptyMessage="The plan appears here once the forecasting engine produces it from sales and stock data. You can still schedule batches below."
            />
          </Card>

          <div className="grid-2">
            <InsightPanel
              title="Production Insight"
              text={loading ? undefined : insights.text}
              emptyText={loading ? 'Loading insights…' : undefined}
            />
            <ActionsPanel title="Next Steps" items={loading ? undefined : list(insights.actions)} emptyText={loading ? 'Loading…' : undefined} />
          </div>
        </>
      )}

      {/* Hidden while the page-level error shows; its Retry reloads the batches too */}
      {!failed && (
        <BatchesTable
          refreshKey={refreshKey}
          stages={options.data?.stages}
          canManage={canManage}
          onNew={() => setScheduling({ row: null })}
          onChanged={refresh}
        />
      )}

      <ScheduleBatchModal
        open={Boolean(scheduling)}
        planRow={scheduling?.row}
        options={options}
        onClose={() => setScheduling(null)}
        onSchedule={schedule}
      />
    </div>
  )
}
