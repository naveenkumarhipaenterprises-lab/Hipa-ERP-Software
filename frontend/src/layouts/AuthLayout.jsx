import { Suspense } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import loginBg from '../assets/login-bg.jpg'
import LanguageSelector from '../components/auth/LanguageSelector'
import Loader from '../components/common/Loader'
import Logo from '../components/common/Logo'
import RouteErrorBoundary from '../components/common/RouteErrorBoundary'

/** Login / password pages: a full-screen spice-farm photo with the logo top-left and a frosted glass card. */
export default function AuthLayout() {
  const { pathname } = useLocation()
  return (
    <div className="auth" style={{ backgroundImage: `url(${loginBg})` }}>
      <div className="auth__brand" aria-hidden>
        <Logo size={128} />
      </div>
      <div className="auth__lang">
        <LanguageSelector />
      </div>
      <section className="auth__panel">
        <main className="auth__card">
          <RouteErrorBoundary key={pathname}>
            <Suspense fallback={<Loader />}>
              <Outlet />
            </Suspense>
          </RouteErrorBoundary>
        </main>
      </section>
    </div>
  )
}
