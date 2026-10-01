import { describe, expect, it } from 'vitest'
import {
  formatByType,
  formatCompact,
  formatDate,
  formatINR,
  formatINRShort,
  formatKg,
  formatPercent,
  formatRelativeTime,
  initials,
} from './formatters'

describe('formatINR', () => {
  it('uses Indian digit grouping', () => {
    expect(formatINR(1234567)).toBe('₹12,34,567')
  })
  it('shows paise only when present, always as two digits', () => {
    expect(formatINR(12500)).toBe('₹12,500')
    expect(formatINR(12500.5)).toBe('₹12,500.50')
    expect(formatINR(0.07)).toBe('₹0.07')
  })
  it('puts the minus sign before the rupee symbol', () => {
    expect(formatINR(-20000)).toBe('-₹20,000')
  })
  it('treats missing or invalid values as zero', () => {
    expect(formatINR(null)).toBe('₹0')
    expect(formatINR('abc')).toBe('₹0')
  })
})

describe('formatINRShort', () => {
  it('abbreviates to K, lakh and crore', () => {
    expect(formatINRShort(85000)).toBe('₹85K')
    expect(formatINRShort(3850000)).toBe('₹38.5L')
    expect(formatINRShort(12000000)).toBe('₹1.2Cr')
    expect(formatINRShort(500)).toBe('₹500')
  })
  it('handles negatives', () => {
    expect(formatINRShort(-250000)).toBe('-₹2.5L')
  })
})

describe('other formatters', () => {
  it('formats kg, compact numbers and percentages', () => {
    expect(formatKg(1200.5)).toBe('1,200.5 kg')
    expect(formatCompact(150000)).toBe('1.5L')
    expect(formatPercent(27.84, 1)).toBe('27.8%')
  })
  it('formats dates as DD Mon YYYY and leaves bad input readable', () => {
    expect(formatDate('2026-09-05')).toBe('05 Sep 2026')
    expect(formatDate('not a date')).toBe('not a date')
  })
  it('describes recent times in words', () => {
    const now = Date.parse('2026-09-25T12:00:00Z')
    expect(formatRelativeTime('2026-09-25T11:59:40Z', now)).toBe('just now')
    expect(formatRelativeTime('2026-09-25T11:55:00Z', now)).toBe('5 minutes ago')
    expect(formatRelativeTime('2026-09-24T12:00:00Z', now)).toBe('yesterday')
    expect(formatRelativeTime('2026-08-01T12:00:00Z', now)).toBe('01 Aug 2026')
  })
  it('builds initials from a name, even when missing', () => {
    expect(initials('Priya Ramesh Kumar')).toBe('PR')
    expect(initials(undefined)).toBe('')
    expect(initials(null)).toBe('')
  })
})

describe('formatByType (formats named by the API)', () => {
  it('applies the requested format', () => {
    expect(formatByType(1500, 'inr')).toBe('₹1,500')
    expect(formatByType(12.5, 'kg')).toBe('12.5 kg')
    expect(formatByType(4.25, 'percent')).toBe('4.3%')
    expect(formatByType('2026-09-20', 'date')).toBe('20 Sep 2026')
    expect(formatByType(1234, 'number')).toBe('1,234')
  })
  it('shows a dash for blanks and plain text for unknown formats', () => {
    expect(formatByType(null, 'inr')).toBe('—')
    expect(formatByType('', 'kg')).toBe('—')
    expect(formatByType('Chennai', 'mystery')).toBe('Chennai')
  })
})
