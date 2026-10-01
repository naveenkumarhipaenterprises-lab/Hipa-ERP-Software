import { Lock } from 'lucide-react'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import EmptyState from '../components/common/EmptyState'
import { useAuth } from '../hooks/useAuth'

/** Requires login; with `module`, also requires the user's role to include that module. */
export default function ProtectedRoute({ module, children }) {
  const { isAuthenticated, sessionExpired, can } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) {
    const from = location.pathname + location.search
    return <Navigate to="/login" replace state={{ from, expired: sessionExpired }} />
  }

  if (module && !can(module)) {
    return (
      <>
        <title>Access Denied | HIPA MASALA</title>
        <EmptyState
          icon={Lock}
          title="You don't have access to this module"
          message="Ask your administrator to update your role if you need it."
          action={
            module !== 'dashboard' && (
              <Link to="/dashboard" className="btn btn--primary btn--md">
                Back to Dashboard
              </Link>
            )
          }
        />
      </>
    )
  }

  return children ?? <Outlet />
}
