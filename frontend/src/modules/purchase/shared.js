import { formatDate, formatINR, formatNumber } from '../../utils/formatters'

// Who may change what (mirrors MODULE_WRITE in backend/apps/core/roles.py; the backend enforces it)
export const PURCHASE_MANAGERS = ['admin', 'management', 'purchase']
export const PAYMENT_MANAGERS = ['admin', 'management', 'purchase', 'finance']
export const STOCK_RECORDERS = ['admin', 'management', 'purchase', 'inventory']

export const PAGE_SIZE = 10

export const list = (v) => (Array.isArray(v) ? v : [])
export const has = (v) => v !== null && v !== undefined && v !== ''
export const dash = (v) => (has(v) ? v : '—')
export const money = (v) => (has(v) ? formatINR(v) : '—')
export const qty = (v, unit) => (has(v) ? `${formatNumber(v)}${unit ? ` ${unit}` : ''}` : '—')
export const date = (v) => (v ? formatDate(v) : '—')
export const pct = (v) => (has(v) ? `${formatNumber(v)}%` : '—')

/** API option lists ({ id, name } or { value, label }) -> <Select> options */
export const idOptions = (items, label = (x) => x.name) => list(items).map((x) => ({ value: String(x.id), label: label(x) }))
export const choiceOptions = (items) => list(items).map((x) => ({ value: String(x.value), label: x.label }))
export const withAll = (label, options) => [{ value: '', label }, ...options]

/** Sends numbers only when filled in, so the backend applies its defaults to blanks. */
export const optionalNumber = (v) => (has(v) ? Number(v) : undefined)
export const optionalText = (v) => (typeof v === 'string' ? v.trim() || undefined : v)
