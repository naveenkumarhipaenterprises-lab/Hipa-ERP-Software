import { ArrowLeft, Mail, MailCheck, RotateCw } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import Button from '../../components/common/Button'
import ErrorMessage from '../../components/common/ErrorMessage'
import Input from '../../components/common/Input'
import Logo from '../../components/common/Logo'
import { authService } from '../../services/authService'
import { isEmail } from '../../utils/validation'

const fieldMessage = (v) => (Array.isArray(v) ? v[0] : typeof v === 'string' ? v : undefined)

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [serverError, setServerError] = useState('')
  const [pending, setPending] = useState(false)
  const [sentTo, setSentTo] = useState('')

  const send = async () => {
    const address = email.trim()
    if (!isEmail(address)) {
      setError('Enter the email address linked to your account')
      return
    }
    setPending(true)
    setServerError('')
    try {
      await authService.forgotPassword(address)
      setSentTo(address)
    } catch (err) {
      const fieldErr = fieldMessage(err.fields?.email)
      if (fieldErr) {
        setSentTo('')
        setError(fieldErr)
      } else setServerError(err.message)
    } finally {
      setPending(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!pending) send()
  }

  const changeEmail = () => {
    setSentTo('')
    setServerError('')
  }

  return (
    <>
      <title>Forgot Password | HIPA MASALA</title>
      <div className="auth__card-head">
        <Logo />
        <h1>{sentTo ? 'Check your email' : 'Forgot Password?'}</h1>
        <p>
          {sentTo ? (
            <>
              If <strong>{sentTo}</strong> is registered, we&apos;ve sent a link to reset your password.
            </>
          ) : (
            "Enter your email and we'll send you a link to reset your password."
          )}
        </p>
      </div>

      {sentTo ? (
        <>
          <div className="auth__success" aria-hidden>
            <MailCheck size={44} />
          </div>
          <ErrorMessage message={serverError} />
          <p className="auth__hint">Didn&apos;t get it? Check your spam folder, or send the link again.</p>
          <div className="auth__actions">
            <Button variant="outline" block icon={RotateCw} loading={pending} onClick={send}>
              {pending ? 'Sending…' : 'Resend Link'}
            </Button>
            <Button variant="ghost" block onClick={changeEmail} disabled={pending}>
              Use a different email
            </Button>
          </div>
        </>
      ) : (
        <form className="login-form" onSubmit={handleSubmit} noValidate aria-busy={pending || undefined}>
          <ErrorMessage message={serverError} />
          <Input
            label="Email"
            type="email"
            icon={Mail}
            placeholder="Enter your registered email"
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            autoFocus
            value={email}
            onChange={(e) => {
              setEmail(e.target.value)
              setError('')
            }}
            error={error}
            disabled={pending}
          />
          <Button type="submit" size="lg" block loading={pending}>
            {pending ? 'Sending…' : 'Send Reset Link'}
          </Button>
        </form>
      )}

      <p className="auth__alt">
        <Link to="/login" className="link link--strong link--icon">
          <ArrowLeft size={16} /> Back to Login
        </Link>
      </p>
    </>
  )
}
