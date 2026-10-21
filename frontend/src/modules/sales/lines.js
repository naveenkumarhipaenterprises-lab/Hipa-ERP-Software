/** Product lines of a quotation, sales invoice or sales order while they are being edited (see components/ProductLines). */

const list = (v) => (Array.isArray(v) ? v : [])
export const has = (v) => v !== null && v !== undefined && v !== ''

let nextKey = 1
export const blankLine = (gst = '') => ({ key: nextKey++, product_id: '', quantity_kg: '', unit_price: '', discount_pct: '', gst_pct: gst })

/** Editable rows from a saved document's items (API detail). */
export const linesFromItems = (items) =>
  list(items).map((i) => ({ key: nextKey++, product_id: String(i.product_id), quantity_kg: i.quantity_kg, unit_price: i.unit_price,
                            discount_pct: i.discount_pct, gst_pct: i.gst_pct }))

/** Problems to show above the lines ([] when they are fine). The server checks the same again. */
export function linesProblems(lines) {
  const problems = []
  const seen = new Set()
  lines.forEach((l, i) => {
    const row = `Row ${i + 1}: `
    if (!l.product_id) problems.push(`${row}choose a product.`)
    else if (seen.has(l.product_id)) problems.push(`${row}this product is already on another line.`)
    seen.add(l.product_id)
    if (!(Number(l.quantity_kg) > 0)) problems.push(`${row}enter a quantity greater than 0.`)
    if (has(l.unit_price) && Number(l.unit_price) < 0) problems.push(`${row}the unit price can't be negative.`)
    for (const k of ['discount_pct', 'gst_pct']) if (has(l[k]) && (Number(l[k]) < 0 || Number(l[k]) > 100)) problems.push(`${row}percentages must be 0–100.`)
  })
  if (lines.length === 0) problems.push('Add at least one product.')
  return problems
}

/** The `items` the API expects; empty price / discount / GST are left out so the server uses its defaults. */
export const linesBody = (lines) =>
  lines.map((l) => ({
    product_id: l.product_id, quantity_kg: Number(l.quantity_kg),
    ...(has(l.unit_price) ? { unit_price: Number(l.unit_price) } : {}),
    ...(has(l.discount_pct) ? { discount_pct: Number(l.discount_pct) } : {}),
    ...(has(l.gst_pct) ? { gst_pct: Number(l.gst_pct) } : {}),
  }))
