import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { safeRedirect } from '../utils/redirect'

/** Login / password pages: signed-in users go back to where they were headed, or the dashboard. */
export default function PublicRoute() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  return isAuthenticated ? <Navigate to={safeRedirect(location.state?.from)} replace /> : <Outlet />
}
