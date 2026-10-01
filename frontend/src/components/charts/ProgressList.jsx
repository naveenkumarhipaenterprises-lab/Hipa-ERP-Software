import ChartEmpty from './ChartEmpty'

/** Horizontal percentage bars. Shows an empty state when there are no items. */
export default function ProgressList({ items, max = 100, format = (v) => `${v}%`, emptyTitle, emptyMessage }) {
  if (!Array.isArray(items) || items.length === 0) {
    return <ChartEmpty height={160} title={emptyTitle} message={emptyMessage} />
  }
  return (
    <ul className="progress-list">
      {items.map((it, i) => (
        <li key={`${it.name}-${i}`}>
          {it.icon}
          <span className="progress-list__name">{it.name}</span>
          <span className="progress-list__track">
            <span className="progress-list__bar" style={{ width: `${Math.min(100, (Number(it.value) / max) * 100) || 0}%`, background: it.color }} />
          </span>
          <span className="progress-list__value">{format(it.value)}</span>
        </li>
      ))}
    </ul>
  )
}
