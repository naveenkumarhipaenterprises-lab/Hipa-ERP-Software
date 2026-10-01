import { useId } from 'react'
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import ChartEmpty from './ChartEmpty'
import ChartTooltip from './ChartTooltip'
import { isChartEmpty } from './chartUtils'

const MAX_TICK = 14
const shortTick = (v) => {
  const s = String(v ?? '')
  return s.length > MAX_TICK ? `${s.slice(0, MAX_TICK - 1)}…` : s
}

/**
 * One chart component for line, area, bar and combo charts.
 * Shows an empty state (never invented values) when `data` has nothing to plot.
 *
 * series: [{ key, name, color, type: 'area'|'line'|'bar', axis?: 'right', dots?: boolean }]
 * barColors: optional per-category colours for a single bar series
 */
export default function SeriesChart({
  data,
  xKey,
  series,
  height = 260,
  yFormatter = (v) => v,
  rightFormatter = (v) => v,
  tooltipFormatter,
  rightDomain,
  showLegend = false,
  barColors,
  barLabels = false,
  barSize,
  xInterval = 'preserveStartEnd',
  emptyTitle,
  emptyMessage,
}) {
  // useId() can contain characters that are invalid inside url(#...)
  const gid = `g${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  const hasRight = series.some((s) => s.axis === 'right')

  if (isChartEmpty(data, series.map((s) => s.key))) {
    return <ChartEmpty height={height} title={emptyTitle} message={emptyMessage} />
  }

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: barLabels ? 22 : 12, right: hasRight ? 4 : barLabels ? 20 : 12, left: 0, bottom: 0 }}>
          <defs>
            {series
              .filter((s) => s.type === 'area')
              .map((s) => (
                <linearGradient key={s.key} id={`${gid}-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={s.color} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
                </linearGradient>
              ))}
          </defs>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis
            dataKey={xKey}
            tickLine={false}
            axisLine={false}
            tick={{ fill: 'var(--muted)', fontSize: 12 }}
            interval={xInterval}
            minTickGap={12}
            // Long category names (e.g. product names) would spill outside the card; the tooltip shows them in full
            tickFormatter={shortTick}
          />
          <YAxis
            yAxisId="left"
            tickLine={false}
            axisLine={false}
            tick={{ fill: 'var(--muted)', fontSize: 12 }}
            tickFormatter={yFormatter}
            width={52}
          />
          {hasRight && (
            <YAxis
              yAxisId="right"
              orientation="right"
              tickLine={false}
              axisLine={false}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
              tickFormatter={rightFormatter}
              domain={rightDomain ?? ['auto', 'auto']}
              width={40}
            />
          )}
          <Tooltip
            cursor={{ stroke: 'var(--border-strong)', fill: 'var(--hover)' }}
            content={
              <ChartTooltip
                formatter={(v, name) => {
                  if (tooltipFormatter) return tooltipFormatter(v, name)
                  const s = series.find((x) => x.name === name)
                  return s?.axis === 'right' ? rightFormatter(v) : yFormatter(v)
                }}
              />
            }
          />
          {showLegend && (
            <Legend
              verticalAlign="top"
              align="center"
              height={30}
              iconType="circle"
              iconSize={9}
              wrapperStyle={{ fontSize: 12.5, color: 'var(--text)' }}
            />
          )}
          {series.map((s) => {
            const common = { dataKey: s.key, name: s.name, yAxisId: s.axis ?? 'left', isAnimationActive: true }
            if (s.type === 'bar')
              return (
                <Bar {...common} key={s.key} fill={s.color} radius={[5, 5, 0, 0]} barSize={barSize} maxBarSize={36}>
                  {barColors && data.map((_, i) => <Cell key={i} fill={barColors[i % barColors.length]} />)}
                  {barLabels && (
                    <LabelList dataKey={s.key} position="top" formatter={yFormatter} style={{ fill: 'var(--text)', fontSize: 12, fontWeight: 600 }} />
                  )}
                </Bar>
              )
            if (s.type === 'area')
              return (
                <Area
                  {...common}
                  key={s.key}
                  type="monotone"
                  stroke={s.color}
                  strokeWidth={2.4}
                  fill={`url(#${gid}-${s.key})`}
                  dot={s.dots ? { r: 3, fill: s.color, strokeWidth: 0 } : false}
                  activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
                />
              )
            return (
              <Line
                {...common}
                key={s.key}
                type="monotone"
                stroke={s.color}
                strokeWidth={2.4}
                dot={s.dots ? { r: 3, fill: s.color, strokeWidth: 0 } : false}
                activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
              />
            )
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
