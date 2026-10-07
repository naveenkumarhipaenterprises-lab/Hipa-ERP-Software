import { KeyRound, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { settingsApi } from '../../../api/settingsApi'
import PasswordInput from '../../../components/auth/PasswordInput'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Toggle } from '../../../components/common/Input'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatTime } from '../../../utils/formatters'
import { validateNewPassword } from '../../../utils/validation'

const EMPTY = { current: '', password: '', confirm: '' }
const fieldMessage = (v) => (Array.isArray(v) ? v[0] : typeof v === 'string' ? v : undefined)

function ChangePassword() {
  const toast = useToast()
  const [values, setValues] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [serverError, setServerError] = useState('')
  const [pending, setPending] = useState(false)

  const set = (name) => (e) => {
    setValues((v) => ({ ...v, [name]: e.target.value }))
    setErrors((er) => ({ ...er, [name]: undefined }))
  }

  const submit = async (e) => {
    e.preventDefault()
    const errs = validateNewPassword(values)
    if (!values.current) errs.current = 'Enter your current password'
    else if (values.password && values.password === values.current) errs.password = 'Choose a password different from the current one'
    setErrors(errs)
    if (Object.keys(errs).length) return
    setPending(true)
    setServerError('')
    try {
      await settingsApi.changePassword({ current_password: values.current, new_password: values.password })
      setValues(EMPTY)
      toast.success('Password changed. Your other devices have been signed out.')
    } catch (err) {
      const f = err.fields
      const next = { current: fieldMessage(f?.current_password), password: fieldMessage(f?.new_password) }
      setErrors(next)
      setServerError(Object.values(next).includes(err.message) ? '' : err.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <form className="settings-password" onSubmit={submit} noValidate aria-busy={pending || undefined}>
      <h3 className="modal__section-title">Change password</h3>
      <ErrorMessage message={serverError} />
      <PasswordInput label="Current password" autoComplete="current-password" value={values.current} onChange={set('current')} error={errors.current} disabled={pending} />
      <PasswordInput label="New password" autoComplete="new-password" value={values.password} onChange={set('password')} error={errors.password} hint="At least 8 characters with a letter and a number" disabled={pending} />
      <PasswordInput label="Confirm new password" autoComplete="new-password" value={values.confirm} onChange={set('confirm')} error={errors.confirm} disabled={pending} />
      <div>
        <Button type="submit" icon={KeyRound} loading={pending}>
          Update Password
        </Button>
      </div>
    </form>
  )
}

/** Password, two-factor authentication and login activity. */
export default function SecuritySection() {
  const toast = useToast()
  const security = useApi(() => settingsApi.getSecurity(), [])
  const [page, setPage] = useState(1)
  const activity = useApi(() => settingsApi.listLoginActivity({ page, page_size: 8 }), [page])
  const rows = Array.isArray(activity.data?.results) ? activity.data.results : []

  const setTwoFactor = async (on) => {
    const before = security.data
    security.setData((d) => ({ ...d, two_factor_enabled: on }))
    try {
      await settingsApi.updateSecurity({ two_factor_enabled: on })
      toast.success(on ? 'Two-factor authentication turned on' : 'Two-factor authentication turned off')
    } catch (err) {
      security.setData(before)
      toast.error(err.message)
    }
  }

  return (
    <>
      <Card title="Security" subtitle="Keep accounts secure">
        {security.error && !security.data ? (
          <ErrorMessage message={security.error.message} onRetry={security.reload} />
        ) : (
          <ul className="setting-list">
            <li>
              <div>
                <strong>
                  <ShieldCheck size={16} aria-hidden /> Two-factor authentication
                </strong>
                <span>Require a one-time code at login for all users</span>
              </div>
              {security.loading && !security.data ? (
                <span className="muted">Loading…</span>
              ) : (
                <Toggle
                  checked={Boolean(security.data?.two_factor_enabled)}
                  onChange={setTwoFactor}
                  label={<span className="sr-only">Two-factor authentication</span>}
                />
              )}
            </li>
          </ul>
        )}
        <ChangePassword />
      </Card>

      <Card title="Login Activity" subtitle="Recent sign-ins across the team" bodyClassName="card__body--flush">
        {activity.error && !activity.loading ? (
          <div className="card__pad">
            <ErrorMessage message={activity.error.message} onRetry={activity.reload} />
          </div>
        ) : (
          <Table
            compact
            loading={activity.loading}
            caption="Login activity"
            data={rows}
            emptyTitle="No login activity recorded"
            emptyMessage="Sign-ins will be listed here."
            pagination={{ page, pageSize: 8, total: Number(activity.data?.count) || 0, onPageChange: setPage }}
            columns={[
              { key: 'user', header: 'User', render: (r) => r.user || '—' },
              { key: 'device', header: 'Device', render: (r) => r.device || '—' },
              { key: 'location', header: 'Location / IP', render: (r) => [r.location, r.ip].filter(Boolean).join(' • ') || '—' },
              { key: 'time', header: 'Time', render: (r) => <span className="nowrap">{r.time ? `${formatDate(r.time)}, ${formatTime(r.time)}` : '—'}</span> },
              { key: 'success', header: 'Result', render: (r) => <Badge tone={r.success === false ? 'red' : 'green'}>{r.success === false ? 'Failed' : 'Success'}</Badge> },
            ]}
          />
        )}
      </Card>
    </>
  )
}
