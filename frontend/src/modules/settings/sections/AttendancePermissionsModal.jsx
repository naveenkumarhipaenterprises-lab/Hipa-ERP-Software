import { useState } from 'react'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Checkbox } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'

/**
 * One user's Attendance permissions (check-in, check-out, leave, employees, calendar, reports, settings). The server
 * enforces every one. A Super Admin always has all of them, so their boxes are shown ticked and locked.
 */
export default function AttendancePermissionsModal({ user, permissions, onClose, onSave }) {
  const isAdmin = user?.role === 'admin'
  const [chosen, setChosen] = useState(() => new Set(user?.attendance_permissions ?? []))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  if (!user) return null

  const toggle = (code, on) => setChosen((s) => {
    const next = new Set(s)
    if (on) next.add(code)
    else next.delete(code)
    return next
  })
  const save = async () => {
    setSaving(true)
    setError('')
    try {
      await onSave(permissions.map((p) => p.value).filter((code) => chosen.has(code)))
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
      title="Attendance permissions"
      subtitle={`${user.name || user.email}${isAdmin ? ' · Super Admin has every permission' : ''}`}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          {!isAdmin && <Button onClick={save} loading={saving}>Save</Button>}
        </>
      }
    >
      <ErrorMessage message={error} />
      <div className="stack">
        {permissions.map((p) =>
          isAdmin ? (
            <label key={p.value} className="checkbox"><input type="checkbox" checked disabled readOnly /><span>{p.label}</span></label>
          ) : (
            <Checkbox key={p.value} label={p.label} checked={chosen.has(p.value)} onChange={(on) => toggle(p.value, on)} />
          ),
        )}
      </div>
    </Modal>
  )
}
