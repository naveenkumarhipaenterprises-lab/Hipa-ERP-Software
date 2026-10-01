import { Link } from 'react-router-dom'

/** White panel with an optional title row. `action` sits on the right of the title. */
export default function Card({ title, subtitle, action, viewAllTo, onViewAll, className = '', bodyClassName = '', children }) {
  const hasHeader = title || action || viewAllTo || onViewAll
  return (
    <section className={`card ${className}`}>
      {hasHeader && (
        <header className="card__header">
          <div>
            {title && <h2 className="card__title">{title}</h2>}
            {subtitle && <p className="card__subtitle">{subtitle}</p>}
          </div>
          <div className="card__actions">
            {action}
            {viewAllTo && (
              <Link to={viewAllTo} className="link">
                View All
              </Link>
            )}
            {onViewAll && (
              <button className="link" onClick={onViewAll}>
                View All
              </button>
            )}
          </div>
        </header>
      )}
      <div className={`card__body ${bodyClassName}`}>{children}</div>
    </section>
  )
}
