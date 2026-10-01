/** Dark tooltip: label on top, one row per series. */
export default function ChartTooltip({ active, payload, label, formatter = (v) => v, labelFormatter }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">{labelFormatter ? labelFormatter(label, payload) : label ?? payload[0].name}</div>
      {payload.map((p) => (
        <div key={p.dataKey ?? p.name} className="chart-tooltip__row">
          <span className="chart-tooltip__dot" style={{ background: p.color ?? p.payload?.fill }} />
          {payload.length > 1 && <span className="chart-tooltip__name">{p.name}</span>}
          <strong>{formatter(p.value, p.name)}</strong>
        </div>
      ))}
    </div>
  )
}
