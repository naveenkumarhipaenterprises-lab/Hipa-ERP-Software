import { BarChart3, Lightbulb, Megaphone, MessageSquare, Package, ShoppingCart, Wallet } from 'lucide-react'
import Card from '../../../components/common/Card'
import EmptyState from '../../../components/common/EmptyState'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { formatRelativeTime } from '../../../utils/formatters'

// Styling only: icon and colour per insight kind
const KIND = {
  sales: { icon: BarChart3, tone: 'green' },
  inventory: { icon: Package, tone: 'orange' },
  purchase: { icon: ShoppingCart, tone: 'blue' },
  marketing: { icon: Megaphone, tone: 'purple' },
  finance: { icon: Wallet, tone: 'teal' },
}
const list = (v) => (Array.isArray(v) ? v : [])

/** AI-generated insights from GET /ai/home/. */
export function AiInsights({ home }) {
  const items = list(home.data?.insights)
  return (
    <Card title="AI Insights for You">
      {home.loading ? (
        <div className="skeleton skeleton--list" aria-label="Loading" />
      ) : home.error ? (
        <ErrorMessage message={home.error.message} onRetry={home.reload} />
      ) : items.length === 0 ? (
        <EmptyState compact icon={Lightbulb} title="No insights yet" message="Insights appear here once the AI engine analyses your data." />
      ) : (
        <ul className="ai-insights">
          {items.map((i, idx) => {
            const meta = KIND[i.kind] ?? { icon: Lightbulb, tone: 'yellow' }
            const Icon = meta.icon
            return (
              <li key={i.id ?? idx}>
                <span className={`ai-insights__icon tone-${meta.tone}`} aria-hidden>
                  <Icon size={18} />
                </span>
                <div>
                  <p className="ai-insights__head">
                    <strong>{i.title}</strong>
                    {i.created_at && <span className="muted">{formatRelativeTime(i.created_at)}</span>}
                  </p>
                  <p>{i.text}</p>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

/** Past conversations from GET /ai/home/; choosing one reopens it. */
export function ConversationList({ home, activeId, onOpen, disabled }) {
  const items = list(home.data?.conversations)
  return (
    <Card title="Recent Conversations">
      {home.loading ? (
        <div className="skeleton skeleton--list" aria-label="Loading" />
      ) : home.error ? null : items.length === 0 ? (
        <EmptyState compact icon={MessageSquare} title="No conversations yet" message="Your chats with the assistant will be saved here." />
      ) : (
        <ul className="convo-list">
          {items.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => onOpen(c.id)} disabled={disabled} aria-current={c.id === activeId || undefined}>
                <MessageSquare size={16} aria-hidden />
                <span className="convo-list__title">{c.title || 'Untitled conversation'}</span>
                {c.updated_at && <small>{formatRelativeTime(c.updated_at)}</small>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
