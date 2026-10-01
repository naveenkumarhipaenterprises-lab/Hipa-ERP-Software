import { ArrowDown, ArrowUp } from 'lucide-react'

const isBlank = (v) => v === null || v === undefined || v === ''

/**
 * KPI tile. tone: green | blue | orange | red | purple | yellow | teal
 * Pass `value` already formatted; when it is null/undefined the card shows an
 * empty state ("—") instead of a number. `change` is only shown when the API provides it.
 * `goodWhenDown` flips the colour of the change (e.g. expenses).
 */
export default function StatCard({
  icon: Icon,
  label,
  value,
  change,
  changeLabel = 'vs last month',
  sub,
  tone = 'green',
  goodWhenDown = false,
  valueTone,
  loading = false,
  emptyText = 'No data available',
}) {
  const empty = !loading && isBlank(value)
  const hasChange = !empty && typeof change === 'number' && Number.isFinite(change)
  const up = change >= 0
  const good = goodWhenDown ? !up : up

  return (
    <div className={`stat-card tone-${tone} ${empty ? 'stat-card--empty' : ''}`} aria-busy={loading || undefined}>
      <div className="stat-card__icon" aria-hidden>
        {Icon && <Icon size={30} strokeWidth={2} />}
      </div>
      <div className="stat-card__body">
        <p className="stat-card__label">{label}</p>
        {loading ? (
          <span className="stat-card__skeleton" aria-label="Loading" />
        ) : (
          <p className={`stat-card__value ${valueTone && !empty ? `text-${valueTone}` : ''}`}>{empty ? '—' : value}</p>
        )}
        {hasChange && (
          <p className="stat-card__change">
            <span className={good ? 'text-up' : 'text-down'}>
              {up ? <ArrowUp size={14} strokeWidth={3} /> : <ArrowDown size={14} strokeWidth={3} />}
              {Math.abs(change)}%
            </span>
            <span className="muted">{changeLabel}</span>
          </p>
        )}
        {empty && <p className="stat-card__sub">{emptyText}</p>}
        {!empty && sub && <p className="stat-card__sub">{sub}</p>}
      </div>
    </div>
  )
}
