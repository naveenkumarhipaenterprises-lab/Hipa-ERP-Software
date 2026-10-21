import { Plus, Trash2 } from 'lucide-react'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Input, { Select } from '../../../components/common/Input'
import TotalsSummary from '../../../components/common/TotalsSummary'
import { formatINR } from '../../../utils/formatters'
import { documentTotals, lineTotals } from '../../../utils/money'
import { blankLine, has } from '../lines'

const list = (v) => (Array.isArray(v) ? v : [])

/**
 * The "Products" section of a quotation, invoice or order: product lines with add / remove and totals that update
 * as you type (the saved totals come from the backend). `locked` shows the lines read-only with `lockedNote`.
 */
export default function ProductLines({ lines, onChange, products, defaultGst = '', locked = false, lockedNote, errors }) {
  const setLine = (key, name, value) => onChange(lines.map((l) => (l.key === key ? { ...l, [name]: value } : l)))
  const priceOf = (l) => (has(l.unit_price) ? l.unit_price : products.find((p) => String(p.id) === String(l.product_id))?.price_per_kg ?? 0)
  const totals = documentTotals(lines.map((l) => ({ quantity: l.quantity_kg, unitPrice: priceOf(l), discountPct: l.discount_pct, gstPct: l.gst_pct })))

  return (
    <div className="form-grid__full stack">
      <h3 className="doc-section">Products</h3>
      {locked && lockedNote && <p className="muted">{lockedNote}</p>}
      {errors && <ErrorMessage message={list(errors).join(' ')} />}
      <div className="lines">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th className="num">Quantity (kg)</th>
              <th className="num">Unit price (₹)</th>
              <th className="num">Discount %</th>
              <th className="num">GST %</th>
              <th className="num">Amount</th>
              <th><span className="sr-only">Remove</span></th>
            </tr>
          </thead>
          <tbody>
            {lines.map((l, i) => {
              const product = products.find((p) => String(p.id) === String(l.product_id))
              const t = lineTotals(l.quantity_kg, priceOf(l), l.discount_pct, l.gst_pct)
              return (
                <tr key={l.key}>
                  <td style={{ minWidth: 220 }}>
                    <Select aria-label={`Product, row ${i + 1}`} value={l.product_id} disabled={locked} placeholder="Select product"
                            onChange={(e) => setLine(l.key, 'product_id', e.target.value)}
                            options={products.map((p) => ({ value: String(p.id), label: p.name }))} />
                  </td>
                  <td><Input aria-label={`Quantity, row ${i + 1}`} type="number" min="0" step="any" inputMode="decimal" value={l.quantity_kg} disabled={locked} onChange={(e) => setLine(l.key, 'quantity_kg', e.target.value)} /></td>
                  <td><Input aria-label={`Unit price, row ${i + 1}`} type="number" min="0" step="any" inputMode="decimal" value={l.unit_price} disabled={locked}
                             placeholder={product ? String(product.price_per_kg) : ''} onChange={(e) => setLine(l.key, 'unit_price', e.target.value)} /></td>
                  <td><Input aria-label={`Discount percent, row ${i + 1}`} type="number" min="0" max="100" step="any" inputMode="decimal" value={l.discount_pct} disabled={locked} placeholder="0" onChange={(e) => setLine(l.key, 'discount_pct', e.target.value)} /></td>
                  <td><Input aria-label={`GST percent, row ${i + 1}`} type="number" min="0" max="100" step="any" inputMode="decimal" value={l.gst_pct} disabled={locked} placeholder="0" onChange={(e) => setLine(l.key, 'gst_pct', e.target.value)} /></td>
                  <td className="num lines__amount">{formatINR(t.total)}</td>
                  <td>
                    {!locked && (
                      <Button size="sm" variant="ghost" icon={Trash2} aria-label={`Remove row ${i + 1}`} disabled={lines.length === 1}
                              onClick={() => onChange(lines.filter((x) => x.key !== l.key))} />
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {!locked && (
        <div>
          <Button size="sm" variant="soft" icon={Plus} onClick={() => onChange([...lines, blankLine(defaultGst)])}>
            Add Product
          </Button>
        </div>
      )}
      <TotalsSummary totals={totals} totalLabel="Grand Total" />
    </div>
  )
}
