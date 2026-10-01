import { Clock } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import LoginForm from '../../components/auth/LoginForm'
import Logo from '../../components/common/Logo'
import { useAuth } from '../../hooks/useAuth'

export default function Login() {
  const { login } = useAuth()
  const location = useLocation()
  const expired = Boolean(location.state?.expired)

  // On success PublicRoute sends the user back to the page they were headed to
  const handleLogin = (values) => login(values)

  return (
    <>
      <title>Login | HIPA MASALA</title>
      <div className="auth__card-head">
        <Logo />
        <h1>Welcome Back!</h1>
        <p>Login to access your HIPA MASALA portal</p>
      </div>

      {expired && (
        <div className="auth__notice" role="status">
          <Clock size={18} />
          <span>Your session has ended. Please log in again to continue.</span>
        </div>
      )}

      <LoginForm onSubmit={handleLogin} />

      <p className="auth__alt">
        New to HIPA MASALA? <strong className="text-brand">Contact your administrator</strong> for an account.
      </p>
    </>
  )
}
