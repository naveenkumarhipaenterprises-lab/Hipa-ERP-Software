/** Tiny inline trend line (pure SVG so it stays cheap inside tables). */
export default function Sparkline({ values: raw, width = 90, height = 26, color = 'var(--green-600)' }) {
  const values = Array.isArray(raw) ? raw.map(Number).filter(Number.isFinite) : []
  // A line needs at least two points
  if (values.length < 2) return <span className="muted">—</span>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const step = width / (values.length - 1)
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(height - 3 - ((v - min) / span) * (height - 6)).toFixed(1)}`)
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <polyline points={points.join(' ')} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}
