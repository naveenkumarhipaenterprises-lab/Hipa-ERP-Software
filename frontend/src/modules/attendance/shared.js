export const list = (v) => (Array.isArray(v) ? v : [])

/** Badge tone for each day status (the server's status keys). */
export const STATUS_TONES = {
  present: 'green', absent: 'red', leave: 'blue', permission: 'purple', not_checked_out: 'amber',
  office_holiday: 'teal', weekly_holiday: 'gray',
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "06:18 PM" from "HH:MM" or an ISO time from the server (already in IST; never converted by the browser). */
export function clock(value) {
  if (!value) return '—'
  const hhmm = value.length > 5 ? value.slice(11, 16) : value
  const [h, m] = hhmm.split(':').map(Number)
  if (Number.isNaN(h)) return '—'
  return `${String(((h + 11) % 12) + 1).padStart(2, '0')}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`
}

/** "08 Oct 2026" from "2026-10-08" or an ISO timestamp (the IST date the server sent). */
export function day(value) {
  if (!value) return '—'
  const [y, m, d] = value.slice(0, 10).split('-')
  return `${d} ${MONTHS[Number(m) - 1]} ${y}`
}

/** "Today", "Tomorrow" or the date, for an ISO timestamp relative to another (both IST, from the server). */
export function whichDay(iso, reference) {
  if (!iso || !reference) return ''
  const a = Date.UTC(...iso.slice(0, 10).split('-').map((n, i) => (i === 1 ? Number(n) - 1 : Number(n))))
  const b = Date.UTC(...reference.slice(0, 10).split('-').map((n, i) => (i === 1 ? Number(n) - 1 : Number(n))))
  const diff = Math.round((a - b) / 86400000)
  return diff === 0 ? 'Today' : diff === 1 ? 'Tomorrow' : diff === -1 ? 'Yesterday' : day(iso)
}
