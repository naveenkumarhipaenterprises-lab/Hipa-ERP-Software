import { Search, UserPlus, Users } from 'lucide-react'
import { useState } from 'react'
import { settingsApi } from '../../../api/settingsApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import AttendancePermissionsModal from './AttendancePermissionsModal'
import ExtraRolesModal from './ExtraRolesModal'
import SetPasswordModal from './SetPasswordModal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useAuth } from '../../../hooks/useAuth'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { useToast } from '../../../hooks/useToast'
import { ROLE_LABELS } from '../../../utils/constants'
import { formatDate, formatNumber } from '../../../utils/formatters'

const PAGE_SIZE = 10
const list = (v) => (Array.isArray(v) ? v : [])
const INACTIVE = /^(inactive|disabled|suspended)$/i

/**
 * Team members: invite, change role or status, extra roles, and set each person's Attendance permissions.
 * You can't change your own role or deactivate yourself.
 */
export default function UsersSection({ options }) {
  const { user: me } = useAuth()
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState(null) // 'new' | user
  const [confirming, setConfirming] = useState(null) // { user, changes }
  const [permsFor, setPermsFor] = useState(null) // user whose Attendance permissions are open
  const [rolesFor, setRolesFor] = useState(null) // user whose extra roles are open
  const [passwordFor, setPasswordFor] = useState(null) // user whose password a Super Admin is setting
  const [refreshKey, setRefreshKey] = useState(0)
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(query)

  const users = useApi(() => settingsApi.listUsers({ page, page_size: PAGE_SIZE, search: query }), [page, query, refreshKey])
  const rows = list(users.data?.results)
  const total = Number(users.data?.count) || 0
  const roles = list(options.data?.roles).length
    ? options.data.roles
    : Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))
  const statuses = list(options.data?.user_statuses)
  const roleLabel = (v) => roles.find((r) => r.value === v)?.label ?? ROLE_LABELS[v] ?? v
  const isMe = (u) => me && (u.id === me.id || (u.email && u.email === me.email))
  const iAmSuperAdmin = me?.role === 'admin'

  const refresh = () => setRefreshKey((k) => k + 1)
  const attendancePermissions = list(options.data?.attendance_permissions)
  const saveAttendancePermissions = async (codes) => {
    await settingsApi.updateUser(permsFor.id, { attendance_permissions: codes })
    toast.success(`Attendance permissions saved for ${permsFor.name || permsFor.email}`)
    refresh()
  }

  const saveExtraRoles = async (extraRoles) => {
    await settingsApi.updateUser(rolesFor.id, { extra_roles: extraRoles })
    toast.success(`Roles saved for ${rolesFor.name || rolesFor.email}`)
    refresh()
  }

  const savePassword = async (password) => {
    await settingsApi.setUserPassword(passwordFor.id, password)
    toast.success(`Password set for ${passwordFor.name || passwordFor.email}`)
    refresh()
  }

  const saveUser = async (values) => {
    if (editing === 'new') {
      await settingsApi.inviteUser({ ...values, name: values.name.trim(), email: values.email.trim() })
      toast.success(`Invitation sent to ${values.email.trim()}`)
      refresh()
      return
    }
    const changes = { name: values.name.trim(), role: values.role, status: values.status }
    // Deactivating someone signs them out, so ask first
    if (values.status && INACTIVE.test(values.status) && !INACTIVE.test(editing.status ?? '')) {
      setConfirming({ user: editing, changes })
      return
    }
    await settingsApi.updateUser(editing.id, changes)
    toast.success(`${changes.name} updated`)
    refresh()
  }

  const confirmDeactivate = async () => {
    await settingsApi.updateUser(confirming.user.id, confirming.changes)
    toast.success(`${confirming.changes.name} deactivated`)
    refresh()
  }

  const self = editing && editing !== 'new' && isMe(editing)
  const fields =
    editing === 'new'
      ? [
          { name: 'name', label: 'Full name', required: true, full: true },
          { name: 'email', label: 'Email', type: 'email', required: true, full: true },
          { name: 'role', label: 'Role', type: 'select', required: true, options: roles, full: true },
        ]
      : [
          { name: 'name', label: 'Full name', required: true, full: true },
          // Your own role and status are locked so you can't lock yourself out
          ...(self ? [] : [{ name: 'role', label: 'Role', type: 'select', required: true, options: roles }]),
          ...(self || statuses.length === 0 ? [] : [{ name: 'status', label: 'Status', type: 'select', required: true, options: statuses }]),
        ]

  return (
    <Card
      title="User Management"
      subtitle={users.loading ? 'Team members and access levels' : `${formatNumber(total)} team member${total === 1 ? '' : 's'}`}
      bodyClassName="card__body--flush"
      action={
        <Button size="sm" icon={UserPlus} onClick={() => setEditing('new')}>
          Invite User
        </Button>
      }
    >
      <div className="toolbar">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name or email" aria-label="Search users" />
        </label>
      </div>

      {users.error && !users.loading ? (
        <div className="card__pad">
          <ErrorMessage message={users.error.message} onRetry={users.reload} />
        </div>
      ) : (
        <Table
          loading={users.loading}
          caption="Users"
          data={rows}
          emptyIcon={Users}
          emptyTitle={query ? 'No users match your search' : 'No users yet'}
          emptyMessage={query ? 'Try a different name or email.' : 'Invite your team to give them access.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
          columns={[
            {
              key: 'name',
              header: 'Name',
              render: (r) => (
                <span>
                  <strong>{r.name || '—'}</strong>
                  {isMe(r) && <span className="muted"> (you)</span>}
                </span>
              ),
            },
            { key: 'email', header: 'Email', render: (r) => r.email || '—' },
            {
              key: 'role',
              header: 'Role',
              render: (r) =>
                r.role ? (
                  <span className="row-actions">
                    <Badge tone="blue">{roleLabel(r.role)}</Badge>
                    {list(r.extra_roles).map((x) => (
                      <Badge key={x}>{`+ ${roleLabel(x)}`}</Badge>
                    ))}
                  </span>
                ) : (
                  '—'
                ),
            },
            { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
            { key: 'last_login', header: 'Last Login', render: (r) => <span className="nowrap">{r.last_login ? formatDate(r.last_login) : 'Never'}</span> },
            {
              key: 'edit',
              sticky: true,
              header: <span className="sr-only">Actions</span>,
              align: 'right',
              render: (r) => (
                <span className="row-actions">
                  {attendancePermissions.length > 0 && (
                    <Button size="sm" variant="ghost" onClick={() => setPermsFor(r)} aria-label={`Attendance permissions for ${r.name || r.email}`}>
                      Attendance
                    </Button>
                  )}
                  {iAmSuperAdmin && !isMe(r) && (
                    <Button size="sm" variant="ghost" onClick={() => setPasswordFor(r)} aria-label={`Set password for ${r.name || r.email}`}>
                      Password
                    </Button>
                  )}
                  {!isMe(r) && r.role !== 'admin' && (
                    <Button size="sm" variant="ghost" onClick={() => setRolesFor(r)} aria-label={`Extra roles for ${r.name || r.email}`}>
                      Roles
                    </Button>
                  )}
                  <Button size="sm" variant="soft" onClick={() => setEditing(r)} aria-label={`Edit ${r.name || r.email}`}>
                    Edit
                  </Button>
                </span>
              ),
            },
          ]}
        />
      )}

      <FormModal
        open={Boolean(editing) && !confirming}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'Invite User' : 'Edit User'}
        subtitle={editing === 'new' ? 'They will receive an email to set their password' : self ? 'You cannot change your own role or status' : editing?.email}
        submitLabel={editing === 'new' ? 'Send Invite' : 'Save'}
        initialValues={editing && editing !== 'new' ? { name: editing.name ?? '', role: editing.role ?? '', status: editing.status ?? '' } : {}}
        fields={fields}
        onSubmit={saveUser}
      />
      <SetPasswordModal key={`pw-${passwordFor?.id}`} user={passwordFor} onClose={() => setPasswordFor(null)} onSave={savePassword} />
      <ExtraRolesModal key={`roles-${rolesFor?.id}`} user={rolesFor} roles={roles} onClose={() => setRolesFor(null)} onSave={saveExtraRoles} />
      <AttendancePermissionsModal key={permsFor?.id} user={permsFor} permissions={attendancePermissions}
                                  onClose={() => setPermsFor(null)} onSave={saveAttendancePermissions} />
      <ConfirmDialog
        open={Boolean(confirming)}
        onClose={() => {
          setConfirming(null)
          setEditing(null)
        }}
        onConfirm={confirmDeactivate}
        danger
        title="Deactivate this user?"
        message={confirming && `${confirming.changes.name} will be signed out and won't be able to log in until reactivated.`}
        confirmLabel="Deactivate"
      />
    </Card>
  )
}
