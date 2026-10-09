import { useState } from 'react'
import PasswordInput from '../../../components/auth/PasswordInput'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Modal from '../../../components/common/Modal'
import { validateNewPassword } from '../../../utils/validation'

const first = (v) => (Array.isArray(v) ? v[0] : typeof v === 'string' ? v : undefined)

/**
 * Super Admin sets another person's password (e.g. a new team member who hasn't set one yet).
 * The server checks the password rules and signs that person out of every device.
 */
export default function SetPasswordModal({ user, onClose, onSave }) {
  const [values, setValues] = useState({ password: '', confirm: '' })
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [saving, setSaving] = useState(false)
  if (!user) return null

  const set = (name) => (e) => {
    setValues((v) => ({ ...v, [name]: e.target.value }))
    setErrors((er) => ({ ...er, [name]: undefined }))
  }
  const save = async (e) => {
    e?.preventDefault()
    const errs = validateNewPassword(values)
    setErrors(errs)
    if (Object.keys(errs).length) return
    setSaving(true)
    setServerError('')
    try {
      await onSave(values.password)
      onClose()
    } catch (err) {
      const msg = first(err.fields?.password)
      setErrors({ password: msg })
      setServerError(msg ? '' : err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Set password"
      subtitle={`${user.name || user.email} · they sign in with ${user.email}`}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={save} loading={saving}>Set Password</Button>
        </>
      }
    >
      <form className="stack" onSubmit={save} noValidate>
        <ErrorMessage message={serverError} />
        <PasswordInput label="New password" autoComplete="new-password" value={values.password} onChange={set('password')}
                       error={errors.password} hint="At least 8 characters with a letter and a number" disabled={saving} />
        <PasswordInput label="Confirm new password" autoComplete="new-password" value={values.confirm} onChange={set('confirm')}
                       error={errors.confirm} disabled={saving} />
        <p className="muted">Share it with them privately. They will be signed out of any open sessions.</p>
      </form>
    </Modal>
  )
}
