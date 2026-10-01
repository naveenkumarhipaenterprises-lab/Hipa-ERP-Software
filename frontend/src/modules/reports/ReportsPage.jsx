import { FileDown, FileSpreadsheet, FileText, IndianRupee, Package, Plus, Printer, ShoppingCart, Users } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { reportsApi } from '../../api/reportsApi'
import Button from '../../components/common/Button'
import DateRangeSelect from '../../components/common/DateRangeSelect'
import EmptyState from '../../components/common/EmptyState'
import ErrorMessage from '../../components/common/ErrorMessage'
import PageHeader from '../../components/common/PageHeader'
import StatCard from '../../components/dashboard/StatCard'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { DATE_RANGES } from '../../utils/constants'
import { formatINR, formatKg, formatNumber } from '../../utils/formatters'
import GenerateReportModal from './components/GenerateReportModal'
import RecentReports from './components/RecentReports'
import ReportPreview from './components/ReportPreview'
import { REPORT_TYPES } from './reportTypes'

const KPIS = [
  { key: 'revenue', label: 'Total Revenue', icon: IndianRupee, tone: 'green', format: formatINR, module: 'sales' },
  { key: 'orders', label: 'Total Orders', icon: ShoppingCart, tone: 'blue', format: formatNumber, module: 'sales' },
  { key: 'customers', label: 'Total Customers', icon: Users, tone: 'orange', format: formatNumber, module: 'customers' },
  { key: 'products_sold_kg', label: 'Products Sold', icon: Package, tone: 'red', format: formatKg, module: 'sales' },
]
const EXPORTS = [
  { format: 'xlsx', label: 'Export as Excel', icon: FileSpreadsheet, className: '' },
  { format: 'pdf', label: 'Export as PDF', icon: FileDown, className: 'btn--tone-red' },
  { format: 'csv', label: 'Export as CSV', icon: FileText, className: 'btn--tone-blue' },
]

const has = (v) => v !== null && v !== undefined && v !== ''

export default function ReportsPage() {
  const { can } = useAuth()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [generating, setGenerating] = useState(false)
  const [exporting, setExporting] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const types = REPORT_TYPES.filter((t) => can(t.module))
  // ?type=inventory etc. opens that report; otherwise the first one the role may see
  const active = types.find((t) => t.key === params.get('type')) ?? types[0]
  const kpis = KPIS.filter((k) => can(k.module))

  const overview = useApi(() => (kpis.length ? reportsApi.getOverview({ range }) : Promise.resolve({})), [range, kpis.length, refreshKey])
  const preview = useApi(() => (active ? reportsApi.getPreview({ type: active.key, range }) : Promise.resolve(null)), [active?.key, range, refreshKey])

  const rangeLabel = DATE_RANGES.find((r) => r.value === range)?.label ?? ''
  const previewReady = !preview.loading && !preview.error && preview.data
  // When the report itself can't load (e.g. backend down) one banner replaces the whole page body
  const failed = Boolean(preview.error) && !preview.loading
  const retryAll = () => setRefreshKey((k) => k + 1)

  const selectType = (key) => setParams({ type: key }, { replace: true })

  const exportAs = async (format) => {
    setExporting(format)
    try {
      await reportsApi.exportPreview({ type: active.key, range, format })
    } catch (err) {
      toast.error(err.message)
    } finally {
      setExporting(null)
    }
  }

  const generate = async (values) => {
    const created = await reportsApi.generate(values)
    toast.success(created?.status && created.status.toLowerCase() !== 'ready' ? 'Report requested. It will be ready to download shortly.' : 'Report generated')
    setRefreshKey((k) => k + 1)
  }

  if (!active) {
    return (
      <div className="page">
        <title>Reports | HIPA MASALA</title>
        <PageHeader icon={FileText} title="Reports" subtitle="Turn your data into better decisions" />
        <EmptyState icon={FileText} title="No reports available for your role" message="Ask your administrator if you need access to a module's reports." />
      </div>
    )
  }

  return (
    <div className="page">
      <title>Reports | HIPA MASALA</title>
      <PageHeader icon={FileText} title="Reports" subtitle="Turn your data into better decisions">
        <DateRangeSelect value={range} onChange={setRange} />
        <Button icon={Plus} onClick={() => setGenerating(true)}>
          Generate Report
        </Button>
      </PageHeader>

      {failed && <ErrorMessage message={preview.error.message} onRetry={retryAll} />}

      {!failed &&
        kpis.length > 0 &&
        (overview.error && !overview.loading ? (
          <ErrorMessage message={overview.error.message} onRetry={overview.reload} />
        ) : (
          <div className="kpi-grid kpi-grid--auto">
            {kpis.map((k) => {
              const kpi = overview.loading ? null : overview.data?.kpis?.[k.key]
              return (
                <StatCard
                  key={k.key}
                  icon={k.icon}
                  tone={k.tone}
                  label={k.label}
                  loading={overview.loading}
                  value={has(kpi?.value) ? k.format(kpi.value) : null}
                  change={kpi?.change}
                  changeLabel="vs prev. period"
                />
              )
            })}
          </div>
        ))}

      <div className="tabs no-print" role="tablist" aria-label="Report type">
        {types.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            id={`report-tab-${t.key}`}
            aria-selected={t.key === active.key}
            aria-controls="report-panel"
            tabIndex={t.key === active.key ? 0 : -1}
            className={`tabs__tab ${t.key === active.key ? 'tabs__tab--active' : ''}`}
            onClick={() => selectType(t.key)}
            onKeyDown={(e) => {
              if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
              const i = types.findIndex((x) => x.key === active.key)
              const next = types[(i + (e.key === 'ArrowRight' ? 1 : types.length - 1)) % types.length].key
              selectType(next)
              document.getElementById(`report-tab-${next}`)?.focus()
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="stack print-area" role="tabpanel" id="report-panel" aria-labelledby={`report-tab-${active.key}`}>
        <h2 className="print-only">
          HIPA MASALA — {active.label} ({rangeLabel})
        </h2>
        {preview.loading ? (
          <div className="skeleton skeleton--table" aria-label="Loading report" />
        ) : (
          !failed && <ReportPreview report={preview.data} label={active.label} />
        )}
      </div>

      <div className="export-bar no-print">
        <div className="export-bar__msg">
          <FileText size={24} aria-hidden />
          <div>
            <strong>{active.label}</strong>
            <span>{rangeLabel} • exported files are generated by the server from the same data</span>
          </div>
        </div>
        <div className="export-bar__btns">
          {EXPORTS.map((x) => (
            <Button
              key={x.format}
              variant="soft"
              className={x.className}
              icon={x.icon}
              loading={exporting === x.format}
              disabled={!previewReady || Boolean(exporting)}
              onClick={() => exportAs(x.format)}
            >
              {x.label}
            </Button>
          ))}
          <Button variant="soft" className="btn--tone-purple" icon={Printer} disabled={!previewReady} onClick={() => window.print()}>
            Print Report
          </Button>
        </div>
      </div>

      {!failed && <RecentReports refreshKey={refreshKey} highlightType={active.key} />}

      <GenerateReportModal
        open={generating}
        types={types}
        defaults={{ type: active.key, range, format: 'pdf' }}
        onClose={() => setGenerating(false)}
        onGenerate={generate}
      />
    </div>
  )
}
