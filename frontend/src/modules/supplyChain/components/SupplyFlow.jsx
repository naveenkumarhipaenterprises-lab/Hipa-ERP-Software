import { ChevronRight, Factory, Leaf, Store, Truck, Warehouse } from 'lucide-react'
import EmptyState from '../../../components/common/EmptyState'
import { formatNumber } from '../../../utils/formatters'

// Styling only: an icon and colour per known stage key
const STAGE_STYLE = {
  farmers: { icon: Leaf, tone: 'green' },
  processing: { icon: Factory, tone: 'orange' },
  warehouse: { icon: Warehouse, tone: 'blue' },
  distribution: { icon: Truck, tone: 'purple' },
  customers: { icon: Store, tone: 'red' },
}

/** Supply chain stages with counts from the API: [{ stage, label, count?, detail? }] */
export default function SupplyFlow({ steps }) {
  const rows = Array.isArray(steps) ? steps : []
  if (rows.length === 0) {
    return <EmptyState compact icon={Truck} title="No flow data yet" message="Counts for each supply chain stage will appear here." />
  }
  return (
    <ol className="flow">
      {rows.map((s, i) => {
        const style = STAGE_STYLE[s.stage] ?? { icon: Truck, tone: 'blue' }
        const Icon = style.icon
        return (
          <li key={s.stage ?? i} className="flow__step">
            <span className={`flow__icon tone-${style.tone}`} aria-hidden>
              <Icon size={24} />
            </span>
            <span className="flow__text">
              <strong>{s.label ?? s.stage}</strong>
              <span>{s.count != null ? formatNumber(s.count) : '—'}</span>
              {s.detail && <small>{s.detail}</small>}
            </span>
            {i < rows.length - 1 && <ChevronRight size={16} className="flow__arrow" aria-hidden />}
          </li>
        )
      })}
    </ol>
  )
}
