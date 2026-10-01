// Paise are shown only when present: ₹12,500 but ₹12,500.50
const rupees = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const rupeesPaise = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const numFormatter = new Intl.NumberFormat('en-IN')

/** ₹38,50,000 (Indian digit grouping); negatives as -₹20,000 */
export const formatINR = (value) => {
  const n = Number(value) || 0
  const a = Math.abs(n)
  const hasPaise = Math.round(a * 100) % 100 !== 0
  return `${n < 0 ? '-' : ''}₹${(hasPaise ? rupeesPaise : rupees).format(a)}`
}

/** ₹38.5L / ₹1.2Cr / ₹85K, for chart axes and tight spaces */
export const formatINRShort = (value) => {
  const n = Number(value) || 0
  const sign = n < 0 ? '-' : ''
  const a = Math.abs(n)
  if (a >= 1e7) return `${sign}₹${trim(a / 1e7)}Cr`
  if (a >= 1e5) return `${sign}₹${trim(a / 1e5)}L`
  if (a >= 1e3) return `${sign}₹${trim(a / 1e3)}K`
  return `${sign}₹${a}`
}

export const formatNumber = (value) => numFormatter.format(Number(value) || 0)

export const formatKg = (value) => `${formatNumber(value)} kg`

export const formatCompact = (value) => {
  const n = Number(value) || 0
  if (n >= 1e5) return `${trim(n / 1e5)}L`
  if (n >= 1e3) return `${trim(n / 1e3)}K`
  return String(n)
}

export const formatPercent = (value, digits = 0) => `${Number(value).toFixed(digits)}%`

/**
 * Formats a value by a format name sent by the API ('inr' | 'number' | 'kg' | 'percent' | 'date').
 * Unknown formats and blanks fall back to plain text / "—".
 */
export const formatByType = (value, format) => {
  if (value === null || value === undefined || value === '') return '—'
  switch (format) {
    case 'inr':
      return formatINR(value)
    case 'number':
      return formatNumber(value)
    case 'kg':
      return formatKg(value)
    case 'percent':
      return formatPercent(value, 1)
    case 'date':
      return formatDate(value)
    default:
      return String(value)
  }
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "10 Dec 2024" from a Date or ISO string */
export const formatDate = (value) => {
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return String(value ?? '')
  return `${String(d.getDate()).padStart(2, '0')} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`
}

/** Local calendar date as YYYY-MM-DD (the format of <input type="date">). */
export const todayISO = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export const formatTime = (value) => {
  const d = value instanceof Date ? value : new Date(value)
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

const relative = new Intl.RelativeTimeFormat('en-IN', { numeric: 'auto' })

/** "5 minutes ago", "yesterday"; falls back to the date for anything older than a week */
export const formatRelativeTime = (value, now = Date.now()) => {
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const secs = Math.round((d.getTime() - now) / 1000)
  const abs = Math.abs(secs)
  if (abs < 45) return 'just now'
  if (abs < 3600) return relative.format(Math.round(secs / 60), 'minute')
  if (abs < 86400) return relative.format(Math.round(secs / 3600), 'hour')
  if (abs < 7 * 86400) return relative.format(Math.round(secs / 86400), 'day')
  return formatDate(d)
}

export const initials = (name) =>
  String(name ?? '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join('')

function trim(n) {
  return Number(n.toFixed(n >= 10 ? 1 : 2)).toString()
}
