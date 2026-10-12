import { useState } from 'react'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Checkbox, Select } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'

/**
 * Roles for one person: either "Attendance only" (check in / out, leave and permission requests, every other access
 * removed), or a main role plus extra roles (e.g. Purchase + Inventory) with the access of every role they hold.
 * The server enforces it. Super Admin already has everything, so it is never chosen here.
 * onSave({ role, extra_roles })
 */
export default function ExtraRolesModal({ user, roles, onClose, onSave }) {
  const isAdmin = user?.role === 'admin'
  const teamRoles = roles.filter((r) => !['admin', 'attendance'].includes(r.value))
  const [attendanceOnly, setAttendanceOnly] = useState(user?.role === 'attendance')
  // Coming back from Attendance only, the person needs a main role again
  const [main, setMain] = useState(user && user.role !== 'attendance' ? user.role : '')
  const [chosen, setChosen] = useState(() => new Set(user?.extra_roles ?? []))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  if (!user) return null

  const extras = teamRoles.filter((r) => r.value !== main)
  const toggle = (value, on) => setChosen((s) => {
    const next = new Set(s)
    if (on) next.add(value)
    else next.delete(value)
    return next
  })
  const save = async () => {
    if (!attendanceOnly && !main) {
      setError('Choose the main role, or tick Attendance only.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSave(attendanceOnly
        ? { role: 'attendance', extra_roles: [] }
        : { role: main, extra_roles: extras.map((r) => r.value).filter((v) => chosen.has(v)) })
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Roles"
      subtitle={`${user.name || user.email}${isAdmin ? ' · Super Admin already has full access' : ''}`}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          {!isAdmin && <Button onClick={save} loading={saving}>Save</Button>}
        </>
      }
    >
      <ErrorMessage message={error} />
      {!isAdmin && (
        <div className="stack">
          <Checkbox label="Attendance only (removes Sales and every other access)" checked={attendanceOnly} onChange={setAttendanceOnly} />
          {attendanceOnly ? (
            <p className="muted">
              This person can only check in / out and request leave or permission. All other roles and module access are removed.
            </p>
          ) : (
            <>
              <Select label="Main role" value={main} onChange={(e) => setMain(e.target.value)} placeholder="Choose the main role"
                      options={teamRoles} />
              <p className="muted">Tick any other areas this person also works in.</p>
              {extras.map((r) => (
                <Checkbox key={r.value} label={r.label} checked={chosen.has(r.value)} onChange={(on) => toggle(r.value, on)} />
              ))}
            </>
          )}
        </div>
      )}
    </Modal>
  )
}
