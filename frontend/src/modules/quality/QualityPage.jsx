import { CalendarCheck, CircleCheck, Clock, Download, FlaskConical, Settings2, ShieldCheck, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { qualityApi } from '../../api/qualityApi'
import DonutChart from '../../components/charts/DonutChart'
import SeriesChart from '../../components/charts/SeriesChart'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import DateRangeSelect, { MiniSelect } from '../../components/common/DateRangeSelect'
import ErrorMessage from '../../components/common/ErrorMessage'
import PageHeader from '../../components/common/PageHeader'
import { ActionsPanel, InsightPanel } from '../../components/dashboard/InsightPanel'
import QuickActions from '../../components/dashboard/QuickActions'
import StatCard from '../../components/dashboard/StatCard'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { CHART_COLORS, DATE_RANGES } from '../../utils/constants'
import { formatDate, formatNumber, formatPercent } from '../../utils/formatters'
import AuditModal from './components/AuditModal'
import AuditsTable from './components/AuditsTable'
import Certifications from './components/Certifications'
import LabProcess from './components/LabProcess'
import QualityTestsTable from './components/QualityTestsTable'
import StandardsModal from './components/StandardsModal'
import TestEntryModal from './components/TestEntryModal'

// Roles that may record tests and schedule audits (the backend enforces the same rule)
const QUALITY_MANAGERS = ['admin', 'management', 'quality']

const GRANULARITY = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
]

const KPIS = [
  { key: 'batches_tested', label: 'Lots Tested', icon: CircleCheck, tone: 'green', format: formatNumber },
  { key: 'pass_rate_pct', label: 'Pass Rate', icon: FlaskConical, tone: 'blue', format: (v) => formatPercent(v, 1) },
  { key: 'failed_batches', label: 'Failed Lots', icon: TriangleAlert, tone: 'red', format: formatNumber, goodWhenDown: true },
  { key: 'avg_testing_hours', label: 'Avg. Testing Time', icon: Clock, tone: 'yellow', format: (v) => `${formatNumber(v)} hrs`, goodWhenDown: true },
]

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''

export default function QualityPage() {
  const { user } = useAuth()
  const toast = useToast()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [granularity, setGranularity] = useState(GRANULARITY[0].value)
  const [modal, setModal] = useState(null) // 'test' | 'standards' | 'audit'
  const [refreshKey, setRefreshKey] = useState(0)
  const [downloading, setDownloading] = useState(false)

  const canManage = QUALITY_MANAGERS.includes(user?.role)
  const overview = useApi(() => qualityApi.getOverview({ range }), [range, refreshKey])
  const trend = useApi(() => qualityApi.getTrend({ range, granularity }), [range, granularity, refreshKey])
  const options = useApi(() => qualityApi.getOptions(), [refreshKey])

  // Never show figures from another range or a failed request
  const loading = overview.loading
  const failed = Boolean(overview.error) && !loading
  const data = !loading && !failed ? (overview.data ?? {}) : null
  const insights = data?.insights ?? {}
  const rangeLabel = DATE_RANGES.find((r) => r.value === range)?.label ?? ''

  const productQuality = list(data?.product_quality).map((p) => ({ name: p.name, value: Number(p.batches) || 0, pass: p.pass_rate_pct }))
  const productTotal = productQuality.reduce((s, p) => s + p.value, 0)

  const refresh = () => setRefreshKey((k) => k + 1)

  const downloadReport = async () => {
    setDownloading(true)
    try {
      await qualityApi.downloadReport({ range })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setDownloading(false)
    }
  }

  const saveTest = async (values) => {
    const test = await qualityApi.createTest(values)
    toast.success(test?.product ? `Result saved for ${test.product}${test.batch_number ? ` lot ${test.batch_number}` : ''}` : 'Test result saved')
    refresh()
  }

  const scheduleAudit = async (values) => {
    await qualityApi.scheduleAudit(values)
    toast.success(`Audit scheduled for ${formatDate(values.date)}`)
    refresh()
  }

  const actions = [
    ...(canManage ? [{ label: 'New Test Entry', icon: FlaskConical, tone: 'green', onClick: () => setModal('test') }] : []),
    { label: 'Download Report', icon: Download, tone: 'blue', onClick: downloadReport },
    { label: 'Quality Standards', icon: Settings2, tone: 'purple', onClick: () => setModal('standards') },
    ...(canManage ? [{ label: 'Schedule Audit', icon: CalendarCheck, tone: 'orange', onClick: () => setModal('audit') }] : []),
  ]

  const skeleton = <div className="skeleton skeleton--chart-inner" aria-label="Loading" />

  return (
    <div className="page">
      <title>Quality | HIPA MASALA</title>
      <PageHeader icon={ShieldCheck} title="Quality Assurance" subtitle="Pure Quality. Trusted Taste.">
        <DateRangeSelect value={range} onChange={setRange} />
        <Button variant="outline" icon={Download} onClick={downloadReport} loading={downloading}>
          Download Report
        </Button>
        {canManage && (
          <Button icon={FlaskConical} onClick={() => setModal('test')}>
            New Test Entry
          </Button>
        )}
      </PageHeader>

      {failed && <ErrorMessage message={overview.error.message} onRetry={refresh} />}

      {!failed && (
        <>
          <div className="kpi-grid">
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

          <div className="dash-row">
            <Card
              title="Quality Trend"
              subtitle={rangeLabel}
              className="dash-row__wide"
              action={<MiniSelect label="Trend granularity" value={granularity} onChange={setGranularity} options={GRANULARITY} />}
            >
              {trend.loading ? (
                skeleton
              ) : trend.error ? (
                <ErrorMessage message={trend.error.message} onRetry={trend.reload} />
              ) : (
                <SeriesChart
                  data={list(trend.data)}
                  xKey="label"
                  showLegend
                  series={[
                    { key: 'batches', name: 'Lots Tested', color: '#86d19a', type: 'bar' },
                    { key: 'pass_rate_pct', name: 'Pass Rate %', color: CHART_COLORS[1], type: 'line', axis: 'right', dots: true },
                  ]}
                  yFormatter={formatNumber}
                  rightFormatter={(v) => `${v}%`}
                  rightDomain={[0, 100]}
                  height={250}
                  emptyTitle="No tests in this period"
                  emptyMessage="Lots tested and the pass rate appear once lab results are recorded."
                />
              )}
            </Card>
            <Card title="Item-wise Quality" subtitle="Lots tested • pass rate">
              {loading ? (
                skeleton
              ) : (
                <DonutChart
                  data={productQuality}
                  valueFormatter={(v) => `${formatNumber(v)} lots`}
                  legendValue={(d) => (has(d.pass) ? formatPercent(d.pass, 0) : '—')}
                  centerValue={formatNumber(productTotal)}
                  centerLabel="Lots"
                  size={170}
                  emptyTitle="No lots tested"
                  emptyMessage="Lots per product or raw material and their pass rate appear here."
                />
              )}
            </Card>
            <Card title="Quality Certifications">{loading ? skeleton : <Certifications items={data?.certifications} />}</Card>
          </div>
        </>
      )}

      {!failed && (
        <div className="grid-main-side">
          <QualityTestsTable refreshKey={refreshKey} results={options.data?.results} />
          <Card title="Lab Testing Process">
            <LabProcess />
          </Card>
        </div>
      )}

      {!failed && <AuditsTable refreshKey={refreshKey} statuses={options.data?.audit_statuses} canManage={canManage} />}

      {!failed && (
        <div className="dash-row">
          <InsightPanel
            title="Quality Insights"
            items={loading ? undefined : list(insights.items).filter((s) => typeof s === 'string' && s.trim())}
            emptyText={loading ? 'Loading insights…' : undefined}
          />
          <ActionsPanel
            title="Corrective Actions"
            items={loading ? undefined : list(insights.actions)}
            emptyText={loading ? 'Loading…' : 'No corrective actions open.'}
          />
          <Card title="Quick Actions">
            <QuickActions actions={actions} columns={2} />
          </Card>
        </div>
      )}

      <TestEntryModal open={modal === 'test'} options={options} onClose={() => setModal(null)} onSave={saveTest} />
      <StandardsModal open={modal === 'standards'} onClose={() => setModal(null)} />
      <AuditModal open={modal === 'audit'} options={options} onClose={() => setModal(null)} onSchedule={scheduleAudit} />
    </div>
  )
}
