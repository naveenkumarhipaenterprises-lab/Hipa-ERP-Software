import { SearchX } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import EmptyState from '../../components/common/EmptyState'
import { useAuth } from '../../hooks/useAuth'

/** Shown for unknown URLs, inside the app shell when signed in, on the auth layout otherwise. */
export default function NotFound() {
  const { isAuthenticated } = useAuth()
  const { pathname } = useLocation()

  return (
    <>
      <title>Page Not Found | HIPA MASALA</title>
      <EmptyState
        icon={SearchX}
        title="Page not found"
        message={
          <>
            There is no page at <code className="not-found__path">{pathname}</code>. It may have been moved, or the
            address may be mistyped.
          </>
        }
        action={
          <Link to={isAuthenticated ? '/dashboard' : '/login'} className="btn btn--primary btn--md">
            {isAuthenticated ? 'Back to Dashboard' : 'Go to Login'}
          </Link>
        }
      />
    </>
  )
}
