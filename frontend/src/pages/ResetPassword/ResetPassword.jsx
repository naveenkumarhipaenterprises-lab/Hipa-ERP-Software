import { ArrowLeft, Check, CircleCheck, LinkIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import PasswordInput from '../../components/auth/PasswordInput'
import Button from '../../components/common/Button'
import ErrorMessage from '../../components/common/ErrorMessage'
import Logo from '../../components/common/Logo'
import { authService } from '../../services/authService'
import { validateNewPassword } from '../../utils/validation'

const fieldMessage = (v) => (Array.isArray(v) ? v[0] : typeof v === 'string' ? v : undefined)

/** Mirrors validateNewPassword so users see each rule as they type. */
const RULES = [
  { label: 'At least 8 characters', test: (p) => p.length >= 8 },
  { label: 'At least one letter', test: (p) => /[A-Za-z]/.test(p) },
  { label: 'At least one number', test: (p) => /\d/.test(p) },
]

function InvalidLink({ message }) {
  return (
    <>
      <title>Reset Link Expired | HIPA MASALA</title>
      <div className="auth__card-head">
        <Logo />
        <h1>Link invalid or expired</h1>
        <p>{message || 'This password reset link can no longer be used. Please request a new one.'}</p>
      </div>
      <div className="auth__success auth__success--warn" aria-hidden>
        <LinkIcon size={40} />
      </div>
      <Link to="/forgot-password" className="btn btn--primary btn--lg btn--block">
        Request New Link
      </Link>
      <p className="auth__alt">
        <Link to="/login" className="link link--strong link--icon">
          <ArrowLeft size={16} /> Back to Login
        </Link>
      </p>
    </>
  )
}

export default function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const uid = params.get('uid') || undefined
  const [values, setValues] = useState({ password: '', confirm: '' })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [tokenError, setTokenError] = useState('')
  const [pending, setPending] = useState(false)
  const [done, setDone] = useState(false)

  const set = (name) => (e) => {
    setValues((v) => ({ ...v, [name]: e.target.value }))
    setErrors((er) => ({ ...er, [name]: undefined }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (pending) return
    const errs = validateNewPassword(values)
    setErrors(errs)
    if (Object.keys(errs).length) return
    setPending(true)
    setServerError('')
    try {
      await authService.resetPassword(token, values.password, uid)
      setDone(true)
    } catch (err) {
      const f = err.fields
      const badLink = fieldMessage(f?.token) || fieldMessage(f?.uid)
      if (badLink) {
        setTokenError(badLink)
        return
      }
      const pwErr = fieldMessage(f?.password) || fieldMessage(f?.new_password)
      setErrors({ password: pwErr })
      setServerError(pwErr && err.message === pwErr ? '' : err.message)
    } finally {
      setPending(false)
    }
  }

  if (!token) return <InvalidLink />
  if (tokenError) return <InvalidLink message={tokenError} />

  return (
    <>
      <title>{`${done ? 'Password Updated' : 'Reset Password'} | HIPA MASALA`}</title>
      <div className="auth__card-head">
        <Logo />
        <h1>{done ? 'Password updated' : 'Set a new password'}</h1>
        <p>{done ? 'You can now log in with your new password.' : 'Choose a strong password you have not used before.'}</p>
      </div>

      {done ? (
        <>
          <div className="auth__success" aria-hidden>
            <CircleCheck size={44} />
          </div>
          <Link to="/login" className="btn btn--primary btn--lg btn--block">
            Go to Login
          </Link>
        </>
      ) : (
        <form className="login-form" onSubmit={handleSubmit} noValidate aria-busy={pending || undefined}>
          <ErrorMessage message={serverError} />
          <PasswordInput
            label="New Password"
            placeholder="Enter a new password"
            autoComplete="new-password"
            autoFocus
            value={values.password}
            onChange={set('password')}
            error={errors.password}
            disabled={pending}
            aria-describedby="password-rules"
          />
          <ul className="pw-rules" id="password-rules" aria-label="Password requirements">
            {RULES.map((r) => {
              const met = r.test(values.password)
              return (
                <li key={r.label} className={met ? 'pw-rules__met' : undefined}>
                  <Check size={14} aria-hidden />
                  {r.label}
                  <span className="sr-only">{met ? ' (met)' : ' (not met)'}</span>
                </li>
              )
            })}
          </ul>
          <PasswordInput
            label="Confirm Password"
            placeholder="Re-enter the new password"
            autoComplete="new-password"
            value={values.confirm}
            onChange={set('confirm')}
            error={errors.confirm}
            disabled={pending}
          />
          <Button type="submit" size="lg" block loading={pending}>
            {pending ? 'Updating…' : 'Update Password'}
          </Button>
          <p className="auth__alt">
            <Link to="/login" className="link link--strong link--icon">
              <ArrowLeft size={16} /> Back to Login
            </Link>
          </p>
        </form>
      )}
    </>
  )
}
