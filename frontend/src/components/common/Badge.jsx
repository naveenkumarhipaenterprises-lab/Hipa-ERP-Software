const TONE_BY_STATUS = {
  green: ['delivered', 'active', 'approved', 'in stock', 'pass', 'passed', 'received', 'paid', 'completed', 'ok', 'connected', 'enabled', 'low',
    'income', 'accepted', 'converted'],
  blue: ['in transit', 'scheduled', 'online', 'sent', 'issued'],
  amber: ['processing', 'low stock', 'pending', 'medium', 'due in 3 days', 'due in 5 days', 'partially received', 'partially paid',
    'pending inspection', 'unpaid'],
  red: ['cancelled', 'critical', 'fail', 'failed', 'hold', 'on hold', 'inactive', 'overdue', 'delayed', 'reorder', 'out of stock', 'high', 'not connected',
    'expense', 'rejected', 'expired'],
}

function toneFor(status) {
  const s = String(status).toLowerCase()
  for (const [tone, list] of Object.entries(TONE_BY_STATUS)) if (list.includes(s)) return tone
  return 'gray'
}

/** Coloured pill for statuses. Tone is inferred from the text unless given. */
export default function Badge({ children, tone, className = '' }) {
  return <span className={`badge badge--${tone ?? toneFor(children)} ${className}`}>{children}</span>
}
