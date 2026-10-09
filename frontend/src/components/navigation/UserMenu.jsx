import { ChevronDown, LogOut, Settings, User } from 'lucide-react'
import { useId, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { ROLE_LABELS, userRoles } from '../../utils/constants'
import { initials } from '../../utils/formatters'
import { useDismiss } from '../../hooks/useDismiss'

/** Avatar button with the signed-in user's details, Settings (if allowed) and Log out. */
export default function UserMenu({ open, onToggle, onClose }) {
  const { user, logout, can } = useAuth()
  const navigate = useNavigate()
  const panelId = useId()
  const wrapRef = useRef(null)
  const buttonRef = useRef(null)
  const [signingOut, setSigningOut] = useState(false)

  useDismiss(wrapRef, open, onClose, buttonRef)

  const displayName = user?.name || user?.username || user?.email || 'Signed in'
  const roleLabel = userRoles(user).map((r) => ROLE_LABELS[r] ?? r).join(' + ')

  const handleLogout = async () => {
    if (signingOut) return
    setSigningOut(true)
    try {
      await logout()
    } finally {
      navigate('/login', { replace: true })
    }
  }

  return (
    <div className="dropdown" ref={wrapRef}>
      <button
        ref={buttonRef}
        className="topbar__user"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={`Account: ${displayName}`}
      >
        <span className="avatar" aria-hidden>
          {initials(user?.name || user?.username) || <User size={18} />}
        </span>
        <span className="topbar__user-text" aria-hidden>
          <strong>{displayName}</strong>
          {roleLabel && <span>{roleLabel}</span>}
        </span>
        <ChevronDown size={16} className="topbar__caret" aria-hidden />
      </button>

      {open && (
        <div className="dropdown__panel" id={panelId}>
          <div className="dropdown__who">
            <strong>{displayName}</strong>
            {user?.email && user.email !== displayName && <span>{user.email}</span>}
            {roleLabel && <span className="dropdown__role">{roleLabel}</span>}
          </div>
          {can('settings') && (
            <Link to="/settings" className="dropdown__item" onClick={onClose}>
              <Settings size={16} aria-hidden /> Settings
            </Link>
          )}
          <button className="dropdown__item dropdown__item--danger" onClick={handleLogout} disabled={signingOut} aria-busy={signingOut || undefined}>
            <LogOut size={16} aria-hidden /> {signingOut ? 'Signing out…' : 'Log out'}
          </button>
        </div>
      )}
    </div>
  )
}
