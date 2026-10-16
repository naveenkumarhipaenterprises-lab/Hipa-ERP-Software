import { Suspense } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Loader from '../components/common/Loader'
import Logo from '../components/common/Logo'
import RouteErrorBoundary from '../components/common/RouteErrorBoundary'

/**
 * Login, forgot-password and reset-password pages: the sunrise spice-farm photo across the whole screen
 * (public/images/login-background.jpg; a warm sky-to-field colour shows until it is added), the HIPA MASALA logo in
 * the upper left, and the form in a frosted-glass card on the right. On tablets and phones the card is centred and
 * carries the only logo.
 */
export default function AuthLayout() {
  const { pathname } = useLocation()
  return (
    <div className="auth">
      <div className="auth__brand" aria-hidden>
        <Logo size={210} />
      </div>
      <main className="auth__card">
        <RouteErrorBoundary key={pathname}>
          <Suspense fallback={<Loader />}>
            <Outlet />
          </Suspense>
        </RouteErrorBoundary>
      </main>
    </div>
  )
}
