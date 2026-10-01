import { CircleCheck, Crosshair, Lightbulb } from 'lucide-react'

/**
 * Blue "AI Insight" panel: a paragraph or a checklist, both from the API.
 * With neither, it shows `emptyText` — never a made-up insight.
 */
export function InsightPanel({
  title = 'AI Insight',
  text,
  items,
  action,
  emptyText = 'No insights available yet. They will appear here once the AI engine is connected.',
}) {
  const hasItems = Array.isArray(items) && items.length > 0
  return (
    <section className="insight-panel">
      <Lightbulb className="insight-panel__icon" size={30} />
      <div className="insight-panel__content">
        <div className="insight-panel__head">
          <h3>{title}</h3>
          {action}
        </div>
        {text && <p>{text}</p>}
        {hasItems && <CheckList items={items} />}
        {!text && !hasItems && <p className="insight-panel__empty">{emptyText}</p>}
      </div>
    </section>
  )
}

/** Green "Recommended Actions" / "Next Steps" panel; items come from the API. */
export function ActionsPanel({ title = 'Recommended Actions', items, emptyText = 'No recommended actions right now.' }) {
  const hasItems = Array.isArray(items) && items.length > 0
  return (
    <section className="actions-panel">
      <Crosshair className="actions-panel__icon" size={30} aria-hidden />
      <div>
        <h3>{title}</h3>
        {hasItems ? <CheckList items={items} /> : <p className="insight-panel__empty">{emptyText}</p>}
      </div>
    </section>
  )
}

export function CheckList({ items }) {
  return (
    <ul className="check-list">
      {items.map((it, i) => (
        <li key={`${i}-${it}`}>
          <CircleCheck size={16} className="check-list__icon" />
          <span>{it}</span>
        </li>
      ))}
    </ul>
  )
}
