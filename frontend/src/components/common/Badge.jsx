const TONE_BY_STATUS = {
  green: ['delivered', 'active', 'approved', 'in stock', 'pass', 'received', 'paid', 'completed', 'ok', 'connected', 'enabled', 'low', 'income'],
  blue: ['in transit', 'scheduled', 'grinding', 'packaging', 'cleaning', 'online'],
  amber: ['processing', 'low stock', 'pending', 'medium', 'due in 3 days', 'due in 5 days'],
  red: ['cancelled', 'critical', 'fail', 'hold', 'inactive', 'overdue', 'delayed', 'reorder', 'high', 'not connected', 'expense'],
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
