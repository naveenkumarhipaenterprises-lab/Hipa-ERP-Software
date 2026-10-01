import { Lock, X } from 'lucide-react'
import { useRef } from 'react'
import { Link, NavLink, useLocation, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useFocusTrap } from '../../hooks/useFocusTrap'
import { NAV_ITEMS } from '../../utils/constants'
import Logo from '../common/Logo'
import SpiceArt from '../common/SpiceArt'

/**
 * Role-filtered module navigation. On desktop it is always visible; with `drawer`
 * (tablet and below) it slides in over the page, traps focus, and closes on Escape.
 */
export default function Sidebar({ id, drawer = false, open = false, onClose }) {
  const { can } = useAuth()
  const { pathname } = useLocation()
  const [params] = useSearchParams()
  const ref = useRef(null)
  const items = NAV_ITEMS.filter((n) => can(n.key))
  const isModal = drawer && open

  useFocusTrap(ref, isModal, {
    onEscape: onClose,
    initialFocus: (panel) => panel?.querySelector('.sidebar__link.active') ?? panel?.querySelector('.sidebar__link'),
  })

  return (
    <aside
      ref={ref}
      id={id}
      className={`sidebar ${open ? 'sidebar--open' : ''}`}
      // Off-screen drawer must not be reachable by Tab or screen readers
      inert={drawer && !open}
      role={isModal ? 'dialog' : undefined}
      aria-modal={isModal || undefined}
      aria-label={isModal ? 'Menu' : undefined}
      tabIndex={-1}
    >
      <div className="sidebar__brand">
        <Logo size={130} />
        {drawer && (
          <button type="button" className="icon-btn sidebar__close" onClick={onClose} aria-label="Close menu">
            <X size={20} />
          </button>
        )}
      </div>

      <nav className="sidebar__nav" aria-label="Main">
        {items.map(({ key, label, path, icon: Icon, children }) => {
          const open = Array.isArray(children) && pathname.startsWith(path)
          const activeTab = params.get('tab') || children?.[0]?.tab
          const subItems = (children ?? []).filter((c) => !c.module || can(c.module))
          return (
            <div key={key}>
              <NavLink to={path} className="sidebar__link" onClick={drawer ? onClose : undefined}>
                <Icon size={20} strokeWidth={2.1} aria-hidden />
                <span>{label}</span>
              </NavLink>
              {open && (
                <div className="sidebar__sub" aria-label={`${label} sections`}>
                  {subItems.map((c) => {
                    const active = c.tab && activeTab === c.tab
                    return (
                      <Link
                        key={c.tab ?? c.to}
                        to={c.to ?? (c.tab === children[0].tab ? path : `${path}?tab=${c.tab}`)}
                        className={`sidebar__sublink ${active ? 'sidebar__sublink--active' : ''}`}
                        aria-current={active ? 'page' : undefined}
                        onClick={drawer ? onClose : undefined}
                      >
                        {c.label}
                      </Link>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
        {items.length === 0 && (
          <p className="sidebar__empty">
            <Lock size={16} aria-hidden />
            No modules are enabled for your role yet. Contact your administrator.
          </p>
        )}
      </nav>

      <div className="sidebar__art" aria-hidden>
        <SpiceArt width={170} />
        <p>
          <strong>Traditional Spices</strong>
          <span>Modern Intelligence</span>
        </p>
      </div>
    </aside>
  )
}
