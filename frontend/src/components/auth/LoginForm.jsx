import { ArrowRight, UserRound } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { validateLogin } from '../../utils/validation'
import Button from '../common/Button'
import ErrorMessage from '../common/ErrorMessage'
import Input, { Checkbox } from '../common/Input'
import PasswordInput from './PasswordInput'

/** Pulls a field-level message out of a DRF error body, e.g. { username: ["..."] }. */
function fieldError(fields, name) {
  const v = fields?.[name]
  if (Array.isArray(v)) return v[0]
  return typeof v === 'string' ? v : undefined
}

export default function LoginForm({ onSubmit }) {
  const [values, setValues] = useState({ username: '', password: '', remember: false })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [pending, setPending] = useState(false)

  const set = (name) => (e) => {
    setValues((v) => ({ ...v, [name]: e.target.value }))
    setErrors((er) => ({ ...er, [name]: undefined }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (pending) return
    const errs = validateLogin(values)
    setErrors(errs)
    if (Object.keys(errs).length) return
    setPending(true)
    setServerError('')
    try {
      await onSubmit({ ...values, username: values.username.trim() })
    } catch (err) {
      const fieldErrs = {
        username: fieldError(err.fields, 'username'),
        password: fieldError(err.fields, 'password'),
      }
      setErrors(fieldErrs)
      // Show the banner unless the server only complained about a specific field
      const onlyField = (fieldErrs.username || fieldErrs.password) && err.message === (fieldErrs.username || fieldErrs.password)
      setServerError(onlyField ? '' : err.message || 'Login failed. Please try again.')
      setValues((v) => ({ ...v, password: '' }))
      setPending(false)
    }
  }

  return (
    <form className="login-form" onSubmit={handleSubmit} noValidate aria-busy={pending || undefined}>
      <ErrorMessage message={serverError} />
      <Input
        label="Email / Username"
        icon={UserRound}
        placeholder="Enter your email or username"
        autoComplete="username"
        autoCapitalize="none"
        spellCheck={false}
        autoFocus
        value={values.username}
        onChange={set('username')}
        error={errors.username}
        disabled={pending}
      />
      <PasswordInput
        placeholder="Enter your password"
        autoComplete="current-password"
        value={values.password}
        onChange={set('password')}
        error={errors.password}
        disabled={pending}
      />
      <div className="login-form__row">
        <Checkbox label="Remember me" checked={values.remember} onChange={(c) => setValues((v) => ({ ...v, remember: c }))} />
        <Link to="/forgot-password" className="link link--strong">
          Forgot Password?
        </Link>
      </div>
      <Button type="submit" size="lg" block loading={pending} iconRight={ArrowRight}>
        {pending ? 'Signing in…' : 'Login'}
      </Button>
    </form>
  )
}
