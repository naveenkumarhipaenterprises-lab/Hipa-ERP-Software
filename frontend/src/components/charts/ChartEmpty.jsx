import { ChartNoAxesColumn } from 'lucide-react'

/** Placeholder that keeps a chart's space when there is no data to plot. */
export default function ChartEmpty({ height = 240, title = 'No data available', message = 'The chart will appear once data is available.' }) {
  return (
    <div className="chart-empty" style={{ minHeight: height }} role="status">
      <ChartNoAxesColumn size={28} aria-hidden />
      <strong>{title}</strong>
      <span>{message}</span>
    </div>
  )
}
