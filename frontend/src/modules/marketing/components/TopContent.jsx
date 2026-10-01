import { ExternalLink, Eye, Heart, ImageOff, Share2 } from 'lucide-react'
import EmptyState from '../../../components/common/EmptyState'
import { formatCompact } from '../../../utils/formatters'

const stat = (v) => (v === null || v === undefined ? '—' : formatCompact(v))

/** Best-performing posts from the API: [{ id, title, platform?, views?, likes?, shares?, url? }] */
export default function TopContent({ items }) {
  const rows = Array.isArray(items) ? items : []
  if (rows.length === 0) {
    return <EmptyState compact icon={ImageOff} title="No content data yet" message="Your best-performing posts will appear here." />
  }
  return (
    <ul className="content-list">
      {rows.slice(0, 4).map((c, i) => (
        <li key={c.id ?? i} className="content-list__item">
          <div className="content-list__head">
            <strong>{c.title}</strong>
            {c.platform && <span className="content-list__platform">{c.platform}</span>}
          </div>
          <ul className="content-list__stats" aria-label="Engagement">
            <li title="Views">
              <Eye size={14} aria-hidden /> {stat(c.views)}
              <span className="sr-only"> views</span>
            </li>
            <li title="Likes">
              <Heart size={14} aria-hidden /> {stat(c.likes)}
              <span className="sr-only"> likes</span>
            </li>
            <li title="Shares">
              <Share2 size={14} aria-hidden /> {stat(c.shares)}
              <span className="sr-only"> shares</span>
            </li>
            {typeof c.url === 'string' && /^https?:\/\//.test(c.url) && (
              <li>
                <a href={c.url} target="_blank" rel="noopener noreferrer" className="link">
                  Open <ExternalLink size={12} aria-hidden />
                </a>
              </li>
            )}
          </ul>
        </li>
      ))}
    </ul>
  )
}
