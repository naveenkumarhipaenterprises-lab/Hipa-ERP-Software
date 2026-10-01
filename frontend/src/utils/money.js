/**
 * Live line totals shown while a form is being filled in: subtotal − discount + GST = total,
 * each rounded to paise the same way as the backend. The saved figures always come from the API.
 */
const round2 = (n) => Math.round((n + Number.EPSILON) * 100) / 100
const num = (v) => {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

export function lineTotals(quantity, unitPrice, discountPct = 0, gstPct = 0) {
  const subtotal = round2(num(quantity) * num(unitPrice))
  const discount = round2((subtotal * num(discountPct)) / 100)
  const gst = round2(((subtotal - discount) * num(gstPct)) / 100)
  return { subtotal, discount, gst, total: round2(subtotal - discount + gst) }
}

/** Sums lineTotals() results for a multi-line document. */
export function documentTotals(lines) {
  return lines.reduce(
    (acc, l) => {
      const t = lineTotals(l.quantity, l.unitPrice, l.discountPct, l.gstPct)
      return {
        subtotal: round2(acc.subtotal + t.subtotal),
        discount: round2(acc.discount + t.discount),
        gst: round2(acc.gst + t.gst),
        total: round2(acc.total + t.total),
      }
    },
    { subtotal: 0, discount: 0, gst: 0, total: 0 },
  )
}
