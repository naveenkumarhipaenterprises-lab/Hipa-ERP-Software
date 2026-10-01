import { formatINR } from '../../utils/formatters'

/**
 * Subtotal / discount / GST / total block for purchase, quotation and invoice forms.
 * `totals` comes from utils/money (live, while typing) or from the API (saved documents).
 */
export default function TotalsSummary({ totals, totalLabel = 'Total', extra = [] }) {
  const rows = [
    { label: 'Subtotal', value: formatINR(totals.subtotal) },
    { label: 'Discount', value: totals.discount ? `− ${formatINR(totals.discount)}` : formatINR(0) },
    { label: 'GST / Tax', value: formatINR(totals.gst) },
    ...extra,
  ]
  return (
    <dl className="totals" aria-label="Totals">
      {rows.map((r) => (
        <div key={r.label} className="totals__row">
          <dt>{r.label}</dt>
          <dd>{r.value}</dd>
        </div>
      ))}
      <div className="totals__row totals__row--grand">
        <dt>{totalLabel}</dt>
        <dd>{formatINR(totals.total)}</dd>
      </div>
    </dl>
  )
}
