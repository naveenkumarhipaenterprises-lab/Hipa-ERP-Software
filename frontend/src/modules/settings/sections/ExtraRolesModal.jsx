import { useState } from 'react'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Checkbox } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'

/**
 * Extra roles for one person on top of their main role (e.g. Purchase + Inventory). They get the access of every role
 * they hold; the server enforces it. Super Admin already has everything, so it is never an extra role.
 */
export default function ExtraRolesModal({ user, roles, onClose, onSave }) {
  const isAdmin = user?.role === 'admin'
  const [chosen, setChosen] = useState(() => new Set(user?.extra_roles ?? []))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  if (!user) return null

  const choices = roles.filter((r) => r.value !== 'admin' && r.value !== user.role)
  const toggle = (value, on) => setChosen((s) => {
    const next = new Set(s)
    if (on) next.add(value)
    else next.delete(value)
    return next
  })
  const save = async () => {
    setSaving(true)
    setError('')
    try {
      await onSave(choices.map((r) => r.value).filter((v) => chosen.has(v)))
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
      title="Extra roles"
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
          <p className="muted">Main role: {roles.find((r) => r.value === user.role)?.label ?? user.role}. Tick any other areas this person also works in.</p>
          {choices.map((r) => (
            <Checkbox key={r.value} label={r.label} checked={chosen.has(r.value)} onChange={(on) => toggle(r.value, on)} />
          ))}
        </div>
      )}
    </Modal>
  )
}
