/** Page title row: big icon, title, subtitle, and actions on the right. */
export default function PageHeader({ icon: Icon, title, subtitle, children, breadcrumb }) {
  return (
    <div className="page-header">
      <div className="page-header__title">
        {Icon && (
          <div className="page-header__icon">
            <Icon size={30} strokeWidth={2.2} />
          </div>
        )}
        <div>
          {breadcrumb && <p className="page-header__crumb">{breadcrumb}</p>}
          <h1>{title}</h1>
          {subtitle && <p className="page-header__sub">{subtitle}</p>}
        </div>
      </div>
      {children && <div className="page-header__actions">{children}</div>}
    </div>
  )
}
