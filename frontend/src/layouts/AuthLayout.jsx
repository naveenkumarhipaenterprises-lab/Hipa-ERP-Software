import { Leaf, ShieldCheck, Sprout } from 'lucide-react'
import { Suspense } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Loader from '../components/common/Loader'
import RouteErrorBoundary from '../components/common/RouteErrorBoundary'
import LanguageSelector from '../components/auth/LanguageSelector'
import Logo from '../components/common/Logo'
import ScriptTagline from '../components/common/ScriptTagline'
import SpiceArt from '../components/common/SpiceArt'

const PROMISES = [
  { icon: Leaf, label: '100% Natural' },
  { icon: ShieldCheck, label: 'Quality Assured' },
  { icon: Sprout, label: 'From Nature to Your Kitchen' },
]

export default function AuthLayout() {
  const { pathname } = useLocation()
  return (
    <div className="auth">
      <section className="auth__hero" aria-hidden>
        <div className="auth__hero-inner">
          <Logo size={170} />
          <h2 className="auth__headline">
            Good Food
            <br />
            Builds Good Lives
          </h2>
          <p className="auth__lead">
            Pure spices. Trusted quality.
            <br />A better tomorrow.
          </p>
          <ul className="auth__promises">
            {PROMISES.map(({ icon: Icon, label }) => (
              <li key={label}>
                <Icon size={30} strokeWidth={1.5} />
                <span>{label}</span>
              </li>
            ))}
          </ul>
        </div>
        <SpiceArt className="auth__art" width={560} />
        <div className="auth__hero-foot">
          <ScriptTagline className="script-tagline--light" />
          <p>
            <strong>HIPA MASALA</strong> | Pure Spices. A Better Tomorrow.
          </p>
        </div>
      </section>

      <section className="auth__panel">
        <div className="auth__lang">
          <LanguageSelector />
        </div>
        <main className="auth__card">
          <RouteErrorBoundary key={pathname}>
            <Suspense fallback={<Loader />}>
              <Outlet />
            </Suspense>
          </RouteErrorBoundary>
        </main>
        <p className="auth__foot">
          <Leaf size={16} /> PURE SPICES <span>|</span> BETTER PEOPLE <span>|</span> BRIGHTER TOMORROW
        </p>
      </section>
    </div>
  )
}
