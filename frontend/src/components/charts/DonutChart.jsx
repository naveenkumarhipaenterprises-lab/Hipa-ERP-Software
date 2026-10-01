import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { CHART_COLORS } from '../../utils/constants'
import ChartEmpty from './ChartEmpty'
import ChartTooltip from './ChartTooltip'

/**
 * Donut with a centre total and a legend beside it.
 * colors: array (by index) or object (by name)
 * Shows an empty state when there are no positive values to plot.
 */
export default function DonutChart({
  data,
  colors = CHART_COLORS,
  centerValue,
  centerLabel,
  valueFormatter = (v) => `${v}%`,
  legendValue,
  size = 190,
  legend = true,
  emptyTitle,
  emptyMessage,
}) {
  if (!Array.isArray(data) || !data.some((d) => Number(d?.value) > 0)) {
    return <ChartEmpty height={size} title={emptyTitle} message={emptyMessage} />
  }

  const colorOf = (d, i) => (Array.isArray(colors) ? colors[i % colors.length] : colors[d.name] ?? CHART_COLORS[i % CHART_COLORS.length])

  return (
    <div className={`donut ${legend ? '' : 'donut--solo'}`}>
      <div className="donut__chart" style={{ width: size, height: size }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="62%"
              outerRadius="100%"
              paddingAngle={1.5}
              stroke="none"
              startAngle={90}
              endAngle={-270}
            >
              {data.map((d, i) => (
                <Cell key={`${d.name}-${i}`} fill={colorOf(d, i)} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip formatter={valueFormatter} />} />
          </PieChart>
        </ResponsiveContainer>
        {(centerValue !== undefined || centerLabel) && (
          <div className="donut__center">
            <strong>{centerValue}</strong>
            <span>{centerLabel}</span>
          </div>
        )}
      </div>
      {legend && (
        <ul className="legend">
          {data.map((d, i) => (
            <li key={`${d.name}-${i}`}>
              <span className="legend__swatch" style={{ background: colorOf(d, i) }} />
              <span className="legend__name">{d.name}</span>
              <span className="legend__value">{legendValue ? legendValue(d) : valueFormatter(d.value)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
