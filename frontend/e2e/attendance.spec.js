import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

const ALL_PERMS = { check_in: true, check_out: true, view_all: true, leave_apply: true, leave_view: true, leave_approve: true,
  leave_reject: true, employee_view: true, employee_manage: true, calendar_view: true, report_view: true, report_export: true,
  settings_view: true, settings_manage: true, holiday_manage: true }
const NO_PERMS = Object.fromEntries(Object.keys(ALL_PERMS).map((k) => [k, false]))
const OWN_ONLY = { ...NO_PERMS, check_in: true, check_out: true }

const OPTIONS = (permissions) => ({
  permissions,
  leave_types: [{ value: 'leave', label: 'Leave' }, { value: 'permission', label: 'Permission' }],
  leave_statuses: [{ value: 'pending', label: 'Pending' }],
  employee_statuses: [{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }],
  day_statuses: [{ value: 'present', label: 'Present' }, { value: 'absent', label: 'Absent' }],
  report_types: [{ value: 'daily', label: 'Daily Attendance' }],
  weekdays: [{ value: 5, label: 'Saturday' }, { value: 6, label: 'Sunday' }],
  departments: [], employees: [], users: [{ id: 7, name: 'TEST Ravi', email: 'ravi@test.invalid' }],
})

const OPEN_MORNING = { is_open: true, checkin_date: '2026-10-08', opens_at: '2026-10-07T17:00:00+05:30',
  closes_at: '2026-10-08T09:20:00+05:30', open_time: '17:00', close_time: '09:20', work_start: '09:00', work_end: '17:30',
  weekly_holiday: 'Sunday', message: null }
const CLOSED = { is_open: false, checkin_date: null, opens_at: '2026-10-08T17:00:00+05:30', closes_at: '2026-10-08T09:20:00+05:30',
  open_time: '17:00', close_time: '09:20', work_start: '09:00', work_end: '17:30', weekly_holiday: 'Sunday',
  message: 'Check-In is closed. It opens again at 5:00 PM.' }

const status = (over = {}) => ({
  server_time: '2026-10-08T08:25:00+05:30',
  timezone: 'Asia/Kolkata (IST)',
  window: OPEN_MORNING,
  employee: { id: 1, employee_code: 'TEST-001', name: 'TEST Worker', department: null },
  work_date: '2026-10-08', office_hours: '9:00 AM – 5:30 PM', scheduled_duration: '08h 30m', holiday: null,
  record: null, can_check_in: true, check_in_for: '2026-10-08', can_check_out: false, checkout_until: null, permissions: OWN_ONLY,
  ...over,
})

const RECORD = { id: 3, attendance_date: '2026-10-08', check_in_at: '2026-10-08T08:25:00+05:30', check_out_at: null,
  scheduled_duration: '08h 30m', total_duration: null, permission_duration: null, working_duration: null, holiday: null, status: 'Checked in' }

const EMPTY_DASHBOARD = { count: 0, results: [], date: '2026-10-08', holiday: null, permission_label: 'Currently On Approved Permission',
  summary: { total_active: 0, present: 0, absent: 0, on_leave: 0, on_permission: 0, not_checked_out: 0 } }

const TODAY = (permissions, statusReply = status({ permissions })) => ({
  ...SHELL,
  'GET /api/attendance/options/': OPTIONS(permissions),
  'GET /api/attendance/status/': statusReply,
  'GET /api/attendance/history/': { count: 0, results: [] },
  'GET /api/attendance/dashboard/': EMPTY_DASHBOARD,
})

test('main menu follows the new order and Attendance has exactly six sections', async ({ page }) => {
  await signIn(page, 'admin')
  await mockApi(page, TODAY(ALL_PERMS))
  await page.goto('/attendance')
  const menu = page.getByRole('navigation', { name: 'Main' })
  await expect(menu.getByRole('link').filter({ hasNotText: /^(Attendance|Employees|Leave \/ Permission|Calendar|Settings|Reports)$/ }))
    .toHaveText(['Dashboard', 'Sales', 'Purchase', 'Inventory', 'Customers', 'Supply Chain', 'Quality', 'Marketing', 'AI Assistant'])
  await expect(page.getByRole('tab')).toHaveText(['Attendance', 'Employees', 'Leave / Permission', 'Calendar', 'Reports', 'Settings'])
  await expect(menu.getByText('Accounts')).toHaveCount(0)
})

test('morning check-in: the server sets the time and check-out is available straight away', async ({ page }) => {
  await signIn(page, 'sales')
  const calls = await mockApi(page, {
    ...TODAY(OWN_ONLY),
    'POST /api/attendance/check-in/': status({ can_check_in: false, can_check_out: true, record: RECORD,
      checkout_until: '2026-10-09T09:20:00+05:30' }),
  })
  await page.goto('/attendance')
  await expect(page.getByRole('heading', { name: 'Check-In Open' })).toBeVisible()
  await expect(page.getByText('09:00 AM – 05:30 PM')).toBeVisible() // office hours
  await expect(page.getByText('No attendance records found.')).toBeVisible()
  await page.getByRole('button', { name: 'Check In', exact: true }).click()
  await expect(page.getByText('Checked in at 08:25 AM')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Check Out / Logout' })).toBeEnabled()
  await expect(page.getByText('Check-out available until tomorrow 09:20 AM.')).toBeVisible()
  expect(calls.find((c) => c.key === 'POST /api/attendance/check-in/').body).toBeFalsy() // no time sent from the browser
  expect(calls.some((c) => c.key === 'GET /api/attendance/dashboard/')).toBe(false) // no View All permission
})

test('evening check-out shows scheduled hours, approved permission and actual working hours', async ({ page }) => {
  await signIn(page, 'sales')
  const evening = { ...OPEN_MORNING, checkin_date: '2026-10-09', opens_at: '2026-10-08T17:00:00+05:30', closes_at: '2026-10-09T09:20:00+05:30' }
  await mockApi(page, {
    ...TODAY(OWN_ONLY, status({ server_time: '2026-10-08T17:30:00+05:30', window: evening, record: RECORD,
      can_check_in: true, check_in_for: '2026-10-09', can_check_out: true, checkout_until: '2026-10-09T09:20:00+05:30' })),
    'POST /api/attendance/check-out/': status({ server_time: '2026-10-08T17:30:00+05:30', window: evening, can_check_out: false,
      can_check_in: true, check_in_for: '2026-10-09', record: { ...RECORD, check_out_at: '2026-10-08T17:30:00+05:30',
        total_duration: '09h 05m', permission_duration: '01h 00m', working_duration: '08h 05m', status: 'Attendance completed' } }),
  })
  await page.goto('/attendance')
  await page.getByRole('button', { name: 'Check Out / Logout' }).click()
  await expect(page.getByText('Checked out at 05:30 PM')).toBeVisible()
  await expect(page.getByText('08h 30m')).toBeVisible() // scheduled
  await expect(page.getByText('08h 05m')).toBeVisible()
  await expect(page.getByText('01h 00m')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Check In for 09 Oct 2026' })).toBeVisible() // the next work day
})

test('Check-In closed from 9:20 AM to 5 PM', async ({ page }) => {
  await signIn(page, 'sales')
  await mockApi(page, TODAY(OWN_ONLY, status({ server_time: '2026-10-08T10:00:00+05:30', can_check_in: false, check_in_for: null, window: CLOSED })))
  await page.goto('/attendance')
  await expect(page.getByRole('heading', { name: 'Check-In Closed' })).toBeVisible()
  await expect(page.getByText('Next opening: Today 05:00 PM')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Check In' })).toBeDisabled()
  await expect(page.getByText('Check-In is closed. It opens again at 5:00 PM.', { exact: true })).toBeVisible()
})

test('check-out after 9:20 AM needs no Attendance permission', async ({ page }) => {
  await signIn(page, 'sales')
  const closed = { server_time: '2026-10-08T09:36:00+05:30', can_check_in: false, check_in_for: null, window: CLOSED, permissions: NO_PERMS }
  await mockApi(page, {
    ...TODAY(NO_PERMS, status({ ...closed, record: { ...RECORD, check_in_at: '2026-10-08T09:12:00+05:30' }, can_check_out: true,
      checkout_until: '2026-10-09T09:20:00+05:30' })),
    'POST /api/attendance/check-out/': status({ ...closed, record: { ...RECORD, check_in_at: '2026-10-08T09:12:00+05:30',
      check_out_at: '2026-10-08T09:36:00+05:30', status: 'Attendance completed' } }),
  })
  await page.goto('/attendance')
  await expect(page.getByText(/permission\./)).toHaveCount(0) // no "You don't have the Check-Out permission."
  await page.getByRole('button', { name: 'Check Out / Logout' }).click()
  await expect(page.getByText('Checked out at 09:36 AM')).toBeVisible()
  await expect(page.getByText('Check-In is closed. It opens again at 5:00 PM.', { exact: true })).toBeVisible() // Check-In stays closed
})

test('dashboard: summary and table for users with View All', async ({ page }) => {
  await signIn(page, 'admin')
  const calls = await mockApi(page, {
    ...TODAY(ALL_PERMS),
    'GET /api/attendance/dashboard/': { ...EMPTY_DASHBOARD, count: 2,
      summary: { total_active: 2, present: 1, absent: 1, on_leave: 0, on_permission: 1, not_checked_out: 0 },
      results: [
        { employee: { id: 1, employee_code: 'TEST-001', name: 'TEST Meena', department: 'Packing' }, date: '2026-10-08',
          check_in_at: '2026-10-08T09:00:00+05:30', check_out_at: '2026-10-08T17:30:00+05:30', scheduled_duration: '08h 30m',
          total_duration: '08h 30m', permission_duration: '01h 00m', working_duration: '07h 30m',
          permission_times: ['4:30 PM – 5:30 PM'], statuses: ['present', 'permission'], labels: ['Present', 'On Permission'] },
        { employee: { id: 2, employee_code: 'TEST-002', name: 'TEST Ravi', department: null }, date: '2026-10-08',
          check_in_at: null, check_out_at: null, scheduled_duration: '08h 30m', total_duration: null, permission_duration: null,
          working_duration: null, permission_times: [], statuses: ['absent'], labels: ['Absent'] },
      ] },
  })
  await page.goto('/attendance')
  const summary = page.getByLabel('Attendance summary')
  await expect(summary.getByText('Total Active Employees')).toBeVisible()
  await expect(summary.getByText('Checked In — Not Checked Out')).toBeVisible()
  await expect(page.getByRole('cell', { name: '07h 30m' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '4:30 PM – 5:30 PM' })).toBeVisible()
  await page.getByLabel('Filter by status').selectOption('absent')
  await expect.poll(() => calls.filter((c) => c.key === 'GET /api/attendance/dashboard/').at(-1).search).toContain('status=absent')
  await page.getByRole('button', { name: 'View TEST Meena' }).click()
  await expect(page.getByRole('dialog', { name: 'TEST Meena' }).getByText('Actual Working Hours')).toBeVisible()
})

test('calendar: add an office holiday', async ({ page }) => {
  await signIn(page, 'admin')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/attendance/options/': OPTIONS(ALL_PERMS),
    'GET /api/attendance/calendar/': { month: '2026-10', employee: { id: 1, employee_code: 'TEST-001', name: 'TEST Worker' },
      days: [{ date: '2026-10-04', statuses: ['weekly_holiday'], labels: ['Weekly Holiday'],
        holiday: { type: 'weekly_holiday', label: 'Weekly Holiday', name: 'Sunday', description: null }, check_in_at: null, check_out_at: null,
        scheduled_duration: '00h 00m', total_duration: null, permission_duration: null, working_duration: null, leaves: [] }],
      holidays: [] },
    'POST /api/attendance/holidays/': { id: 1, name: 'TEST Diwali', date: '2026-10-20', description: null },
  })
  await page.goto('/attendance?tab=calendar')
  await expect(page.getByText('No office holidays this month.')).toBeVisible()
  await expect(page.getByRole('button', { name: '04 Oct 2026: Weekly Holiday' })).toBeVisible()
  await page.getByRole('button', { name: 'Add Office Holiday' }).click()
  const form = page.getByRole('dialog', { name: 'Add Office Holiday' })
  await form.getByLabel(/Holiday Name/).fill('TEST Diwali')
  await form.getByLabel(/^Date/).fill('2026-10-20')
  await form.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('TEST Diwali added')).toBeVisible()
  expect(calls.find((c) => c.key === 'POST /api/attendance/holidays/').body).toMatchObject({ name: 'TEST Diwali', date: '2026-10-20' })
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

test('employees: View Employees alone can look but not change', async ({ page }) => {
  await signIn(page, 'sales')
  await mockApi(page, {
    ...SHELL,
    'GET /api/attendance/options/': OPTIONS({ ...NO_PERMS, employee_view: true }),
    'GET /api/attendance/employees/': { count: 1, results: [{ id: 4, employee_code: 'TEST-004', name: 'TEST Meena', department: 'Packing',
      designation: null, email: null, phone: null, joining_date: null, status: 'Active', status_value: 'active', user: null }] },
  })
  await page.goto('/attendance?tab=employees')
  await expect(page.getByRole('cell', { name: 'TEST Meena', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add Employee' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Delete TEST Meena' })).toHaveCount(0)
})

test('sections without permission are hidden; check-in / check-out stays', async ({ page }) => {
  await signIn(page, 'sales')
  const calls = await mockApi(page, TODAY(NO_PERMS, status({ permissions: NO_PERMS })))
  await page.goto('/attendance?tab=employees')
  await expect(page.getByRole('tab')).toHaveText(['Attendance'])
  await expect(page.getByRole('button', { name: 'Check In', exact: true })).toBeEnabled()
  expect(calls.some((c) => c.key === 'GET /api/attendance/employees/')).toBe(false)
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
