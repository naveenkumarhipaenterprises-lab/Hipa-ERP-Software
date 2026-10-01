import { FileText } from 'lucide-react'
import DonutChart from '../../../components/charts/DonutChart'
import SeriesChart from '../../../components/charts/SeriesChart'
import Card from '../../../components/common/Card'
import EmptyState from '../../../components/common/EmptyState'
import Table from '../../../components/common/Table'
import { CHART_COLORS } from '../../../utils/constants'
import { formatByType, formatINRShort, formatCompact } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])
const axisFormat = (format) => (format === 'inr' ? formatINRShort : format === 'percent' ? (v) => `${v}%` : formatCompact)

/**
 * Draws a report exactly as the server describes it (see reportsApi): a chart,
 * a breakdown donut and a data table. Nothing is calculated here.
 */
export default function ReportPreview({ report, label }) {
  const chart = report?.chart
  const breakdown = report?.breakdown
  const table = report?.table
  const columns = list(table?.columns).map((c) => ({
    key: c.key,
    header: c.header ?? c.key,
    align: c.align ?? (['inr', 'number', 'kg', 'percent'].includes(c.format) ? 'right' : undefined),
    render: (row) => formatByType(row[c.key], c.format),
  }))
  const hasAnything = chart || breakdown || columns.length > 0

  if (!hasAnything) {
    return (
      <Card>
        <EmptyState icon={FileText} title="No data for this report yet" message="The report fills in once the backend has records for this period." />
      </Card>
    )
  }

  return (
    <>
      {(chart || breakdown) && (
        <div className="dash-row">
          {chart && (
            <Card title={chart.title} className="dash-row__wide">
              <SeriesChart
                data={list(chart.data)}
                xKey={chart.x_key}
                showLegend={list(chart.series).length > 1}
                series={list(chart.series).map((s, i) => ({
                  key: s.key,
                  name: s.name ?? s.key,
                  color: CHART_COLORS[i % CHART_COLORS.length],
                  type: ['bar', 'line', 'area'].includes(chart.kind) ? chart.kind : 'bar',
                  dots: chart.kind !== 'bar',
                }))}
                yFormatter={axisFormat(chart.format)}
                tooltipFormatter={(v) => formatByType(v, chart.format)}
                height={260}
                emptyTitle="Nothing to chart for this period"
                emptyMessage="Try a different date range."
              />
            </Card>
          )}
          {breakdown && (
            <Card title={breakdown.title}>
              <DonutChart
                data={list(breakdown.data).map((d) => ({ name: d.name, value: Number(d.value) || 0 }))}
                valueFormatter={(v) => formatByType(v, breakdown.format)}
                size={170}
                emptyTitle="No breakdown for this period"
                emptyMessage="Try a different date range."
              />
            </Card>
          )}
        </div>
      )}

      <Card title={`${label} Data`} bodyClassName="card__body--flush">
        <Table
          compact
          numbered
          pageSize={15}
          caption={`${label} data`}
          data={list(table?.rows)}
          columns={columns.length ? columns : [{ key: 'none', header: 'Data' }]}
          emptyTitle="No rows for this period"
          emptyMessage="Try a different date range."
        />
      </Card>
    </>
  )
}
