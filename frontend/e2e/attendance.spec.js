import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

const ALL_PERMS = { check_in: true, check_out: true, leave_apply: true, leave_view: true, leave_approve: true, leave_reject: true,
  employee_manage: true, calendar_view: true, report_view: true, settings_manage: true }
const NO_PERMS = Object.fromEntries(Object.keys(ALL_PERMS).map((k) => [k, false]))

const OPTIONS = (permissions) => ({
  permissions,
  leave_types: [{ value: 'leave', label: 'Leave' }, { value: 'permission', label: 'Permission' }],
  leave_statuses: [{ value: 'pending', label: 'Pending' }],
  employee_statuses: [{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }],
  day_statuses: [{ value: 'present', label: 'Present' }],
  report_types: [{ value: 'daily', label: 'Daily Attendance' }],
  departments: [], employees: [], users: [{ id: 7, name: 'TEST Ravi', email: 'ravi@test.invalid' }],
})

const status = (over = {}) => ({
  server_time: '2026-10-08T18:25:00+05:30',
  timezone: 'Asia/Kolkata (IST)',
  window: { is_open: true, attendance_date: '2026-10-08', opens_at: '2026-10-08T17:00:00+05:30', closes_at: '2026-10-09T09:20:00+05:30',
    open_time: '17:00', close_time: '09:20', message: null },
  employee: { id: 1, employee_code: 'TEST-001', name: 'TEST Worker', department: null },
  record: null, can_check_in: true, can_check_out: false, permissions: ALL_PERMS,
  ...over,
})

test('main menu follows the new order and Attendance has exactly six sections', async ({ page }) => {
  await signIn(page, 'admin')
  await mockApi(page, { ...SHELL, 'GET /api/attendance/options/': OPTIONS(ALL_PERMS), 'GET /api/attendance/status/': status(),
    'GET /api/attendance/history/': { count: 0, results: [] } })
  await page.goto('/attendance')
  const menu = page.getByRole('navigation', { name: 'Main' })
  await expect(menu.getByRole('link').filter({ hasNotText: /^(Attendance|Employees|Leave \/ Permission|Calendar|Settings|Reports)$/ }))
    .toHaveText(['Dashboard', 'Sales', 'Purchase', 'Inventory', 'Customers', 'Supply Chain', 'Quality', 'Marketing', 'AI Assistant'])
  await expect(page.getByRole('tab')).toHaveText(['Attendance', 'Employees', 'Leave / Permission', 'Calendar', 'Reports', 'Settings'])
  await expect(menu.getByText('Accounts')).toHaveCount(0)
})

test('check in while open: the server sets the time and the button turns into Check Out / Logout', async ({ page }) => {
  await signIn(page, 'sales')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/attendance/options/': OPTIONS(ALL_PERMS),
    'GET /api/attendance/status/': status(),
    'GET /api/attendance/history/': { count: 0, results: [] },
    'POST /api/attendance/check-in/': status({ can_check_in: false, can_check_out: true,
      record: { id: 3, attendance_date: '2026-10-08', check_in_at: '2026-10-08T18:25:00+05:30', check_out_at: null, duration: null, status: 'Checked in' } }),
  })
  await page.goto('/attendance')
  await expect(page.getByRole('heading', { name: 'Attendance Open' })).toBeVisible()
  await expect(page.getByText('No attendance records found.')).toBeVisible()
  await page.getByRole('button', { name: 'Check In' }).click()
  await expect(page.getByText('Checked in at 06:25 PM')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Check Out / Logout' })).toBeEnabled()
  expect(calls.find((c) => c.key === 'POST /api/attendance/check-in/').body).toBeFalsy() // no time sent from the browser
})

test('closed window: shows the next opening and disables check-in', async ({ page }) => {
  await signIn(page, 'sales')
  await mockApi(page, {
    ...SHELL,
    'GET /api/attendance/options/': OPTIONS(ALL_PERMS),
    'GET /api/attendance/status/': status({ server_time: '2026-10-08T10:00:00+05:30', can_check_in: false,
      window: { is_open: false, attendance_date: null, opens_at: '2026-10-08T17:00:00+05:30', closes_at: '2026-10-08T09:20:00+05:30',
        open_time: '17:00', close_time: '09:20', message: 'Attendance is closed. Today\'s attendance window closed at 09:20 AM; it opens again at 05:00 PM.' } }),
    'GET /api/attendance/history/': { count: 0, results: [] },
  })
  await page.goto('/attendance')
  await expect(page.getByRole('heading', { name: 'Attendance Closed' })).toBeVisible()
  await expect(page.getByText('Next opening: Today 05:00 PM')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Check In' })).toBeDisabled()
})

test('employees: add, and delete asks for confirmation; no permission shows a message', async ({ page }) => {
  await signIn(page, 'admin')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/attendance/options/': OPTIONS(ALL_PERMS),
    'GET /api/attendance/employees/': { count: 1, results: [{ id: 4, employee_code: 'TEST-004', name: 'TEST Meena', department: 'Packing',
      designation: null, email: null, phone: null, joining_date: null, status: 'Active', status_value: 'active', user: null }] },
    'POST /api/attendance/employees/': { id: 5, name: 'TEST Ravi' },
    'DELETE /api/attendance/employees/4/': {},
  })
  await page.goto('/attendance?tab=employees')
  await page.getByRole('button', { name: 'Add Employee' }).click()
  const form = page.getByRole('dialog', { name: 'Add Employee' })
  await form.getByLabel(/Employee ID/).fill('TEST-005')
  await form.getByLabel(/Employee Name/).fill('TEST Ravi')
  await form.getByLabel(/Portal login/).selectOption('7')
  await form.getByRole('button', { name: 'Add Employee' }).click()
  await expect(page.getByText('TEST Ravi added')).toBeVisible()
  expect(calls.find((c) => c.key === 'POST /api/attendance/employees/').body).toMatchObject({ employee_code: 'TEST-005', name: 'TEST Ravi', user_id: '7', status: 'active' })
  await page.getByRole('button', { name: 'Delete TEST Meena' }).click()
  await expect(page.getByText('Are you sure you want to delete this employee?')).toBeVisible()
  await page.getByRole('dialog', { name: 'Delete employee?' }).getByRole('button', { name: 'Delete' }).click()
  await expect(page.getByText('TEST Meena deleted')).toBeVisible()
})

test('employees section without permission', async ({ page }) => {
  await signIn(page, 'sales')
  await mockApi(page, { ...SHELL, 'GET /api/attendance/options/': OPTIONS(NO_PERMS), 'GET /api/attendance/employees/': { status: 403, body: { detail: 'TEST' } } })
  await page.goto('/attendance?tab=employees')
  await expect(page.getByText("You don't have permission for this section")).toBeVisible()
})

test('a permission request is submitted with its times', async ({ page }) => {
  await signIn(page, 'sales')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/attendance/options/': OPTIONS({ ...NO_PERMS, leave_apply: true }),
    'GET /api/attendance/leave/': { count: 0, results: [] },
    'POST /api/attendance/leave/': { id: 1 },
  })
  await page.goto('/attendance?tab=leave')
  await expect(page.getByText('No leave or permission requests found.')).toBeVisible()
  await page.getByRole('button', { name: 'New Request' }).click()
  const form = page.getByRole('dialog', { name: 'Leave / Permission Request' })
  await form.getByLabel(/Type/).selectOption('permission')
  await form.getByLabel(/^Date/).fill('2026-10-12')
  await form.getByLabel(/From Time/).fill('10:00')
  await form.getByLabel(/To Time/).fill('12:00')
  await form.getByLabel(/Reason/).fill('TEST personal work')
  await form.getByRole('button', { name: 'Submit Request' }).click()
  await expect(page.getByText('Request submitted')).toBeVisible()
  expect(calls.find((c) => c.key === 'POST /api/attendance/leave/').body).toMatchObject({ type: 'permission', date: '2026-10-12',
    from_time: '10:00', to_time: '12:00', reason: 'TEST personal work' })
})

test('attendance permissions are set per user in Settings → Users', async ({ page }) => {
  await signIn(page, 'admin')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/settings/options/': { roles: [{ value: 'sales', label: 'Sales Team' }], user_statuses: [],
      attendance_permissions: [{ value: 'check_in', label: 'Check in' }, { value: 'check_out', label: 'Check out / logout' }] },
    'GET /api/settings/users/': { count: 1, results: [{ id: 9, name: 'TEST Priya', email: 'priya@test.invalid', role: 'sales', status: 'Active',
      attendance_permissions: ['check_out'] }] },
    'PATCH /api/settings/users/9/': { id: 9 },
  })
  await page.goto('/settings?section=users')
  await page.getByRole('button', { name: 'Attendance permissions for TEST Priya' }).click()
  const dialog = page.getByRole('dialog', { name: 'Attendance permissions' })
  await dialog.getByLabel('Check in').check()
  await dialog.getByLabel('Check out / logout').uncheck()
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Attendance permissions saved for TEST Priya')).toBeVisible()
  expect(calls.find((c) => c.key === 'PATCH /api/settings/users/9/').body).toEqual({ attendance_permissions: ['check_in'] })
})
