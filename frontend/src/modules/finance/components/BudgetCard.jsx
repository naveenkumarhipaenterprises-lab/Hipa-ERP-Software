import { Target } from 'lucide-react'
import Button from '../../../components/common/Button'
import EmptyState from '../../../components/common/EmptyState'
import { formatINRShort } from '../../../utils/formatters'

/** One actual-vs-target bar. The percentage is worked out from the API's actual and target. */
function Meter({ label, actual, target, tone }) {
  const hasTarget = Number(target) > 0
  const pct = hasTarget ? Math.round((Number(actual) / Number(target)) * 100) : null
  return (
    <div className="budget__item">
      <div className="budget__row">
        <span>{label}</span>
        <span>
          {actual != null ? formatINRShort(actual) : '—'} / {hasTarget ? formatINRShort(target) : 'no target'}
        </span>
      </div>
      <div
        className="meter"
        role="meter"
        aria-label={`${label} against budget`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct ?? undefined}
        aria-valuetext={pct == null ? 'No target set' : `${pct}%`}
      >
        <span className={`meter__fill meter__fill--${tone}`} style={{ width: `${Math.min(100, pct ?? 0)}%` }} />
      </div>
      <p className={`budget__pct text-${tone === 'green' ? 'up' : 'down'}`}>{pct == null ? '—' : `${pct}%`}</p>
    </div>
  )
}

/** Budget vs actual for the current period: { period_label, revenue: { actual, target }, expenses: { actual, target } } */
export default function BudgetCard({ budget, onSetBudget }) {
  if (!budget) {
    return (
      <EmptyState
        compact
        icon={Target}
        title="No budget set"
        message="Set a revenue target and expense limit to track progress here."
        action={
          onSetBudget && (
            <Button size="sm" onClick={onSetBudget}>
              Set Budget
            </Button>
          )
        }
      />
    )
  }
  return (
    <div className="budget">
      <Meter label="Revenue" actual={budget.revenue?.actual} target={budget.revenue?.target} tone="green" />
      <Meter label="Expenses" actual={budget.expenses?.actual} target={budget.expenses?.target} tone="red" />
    </div>
  )
}
