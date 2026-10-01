import { describe, expect, it } from 'vitest'
import { toCSV } from './exporters'

describe('toCSV', () => {
  it('writes a header row and quotes values containing commas, quotes or line breaks', () => {
    const csv = toCSV(
      [
        { product: 'Chilli, Kashmiri', note: 'Grade "A"', qty: 12.5 },
        { product: 'Turmeric', note: 'line1\nline2', qty: null },
      ],
      [
        { key: 'product', header: 'Product' },
        { key: 'note', header: 'Note' },
        { key: 'qty', header: 'Qty (kg)' },
      ],
    )
    expect(csv).toBe('Product,Note,Qty (kg)\r\n"Chilli, Kashmiri","Grade ""A""",12.5\r\nTurmeric,"line1\nline2",')
  })

  it('can compute a column from the row', () => {
    expect(toCSV([{ a: 2 }], [{ key: 'x', header: 'Double', value: (r) => r.a * 2 }])).toBe('Double\r\n4')
  })
})
