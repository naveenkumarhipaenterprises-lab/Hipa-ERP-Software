import { describe, expect, it } from 'vitest'
import { documentTotals, lineTotals } from './money'

describe('lineTotals', () => {
  it('applies discount before GST, like the backend', () => {
    // 100 kg x 120 = 12000, -5% = 11400, +5% GST = 11970
    expect(lineTotals(100, 120, 5, 5)).toEqual({ subtotal: 12000, discount: 600, gst: 570, total: 11970 })
  })

  it('treats blanks as zero instead of NaN', () => {
    expect(lineTotals('', '', '', '')).toEqual({ subtotal: 0, discount: 0, gst: 0, total: 0 })
    expect(lineTotals(2, 10)).toEqual({ subtotal: 20, discount: 0, gst: 0, total: 20 })
  })

  it('rounds to paise', () => {
    expect(lineTotals(120.5, 250, 5, 5).total).toBe(30049.69)
  })
})

describe('documentTotals', () => {
  it('adds the lines', () => {
    const t = documentTotals([
      { quantity: 10, unitPrice: 250, discountPct: 10, gstPct: 5 },
      { quantity: 5, unitPrice: 320, discountPct: 0, gstPct: 5 },
    ])
    expect(t).toEqual({ subtotal: 4100, discount: 250, gst: 192.5, total: 4042.5 })
  })
})
