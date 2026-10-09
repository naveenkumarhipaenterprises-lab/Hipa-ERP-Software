import { api, cleanParams as clean } from './client'

/**
 * Attendance endpoints (Django REST API). The server decides everything time-related: whether Check-In is open,
 * and every check-in / check-out time. Nothing time-related is ever sent from the browser.
 *
 * GET  /attendance/status/     -> { server_time, timezone, window: { is_open, checkin_date, opens_at, closes_at, open_time,
 *                                   close_time, work_start, work_end, weekly_holiday, message }, employee, work_date,
 *                                   office_hours, scheduled_duration, holiday, record, can_check_in, check_in_for,
 *                                   can_check_out, checkout_until, permissions }
 *      record: { attendance_date (the work day), check_in_at, check_out_at, scheduled_duration, total_duration,
 *                permission_duration, working_duration, holiday, status }
 *      working = total − approved permission inside office hours; check-out works at any time until 09:20 AM next morning
 * POST /attendance/check-in/   -> status            POST /attendance/check-out/  -> status
 * GET  /attendance/history/    -> own records        GET /attendance/records/   -> everyone's (reports permission)
 * GET  /attendance/dashboard/?date=&employee=&department=&status=&search=&page=   (view_all)
 *      -> { count, results: [{ employee, check_in_at, check_out_at, scheduled_duration, permission_duration,
 *           working_duration, permission_times, statuses, labels }], summary, date, holiday, permission_label }
 * GET  /attendance/options/    -> { permissions, leave_types, leave_statuses, employee_statuses, day_statuses, report_types,
 *                                   weekdays, departments, employees, users }
 * Employees  GET/POST /attendance/employees/  ·  GET/PATCH/DELETE /attendance/employees/<id>/   (delete keeps history)
 * Leave      GET/POST /attendance/leave/?scope=all&status=  ·  PATCH /attendance/leave/<id>/  ·  POST .../<id>/approve|reject|cancel/
 * Calendar   GET /attendance/calendar/?month=YYYY-MM&employee=   -> { month, employee, days, holidays }
 * Holidays   GET/POST /attendance/holidays/?year=  ·  PATCH/DELETE /attendance/holidays/<id>/   { name, date, description }
 * Reports    GET /attendance/reports/?type=daily|monthly|employee|leave&date_from=&date_to=&employee=&department=&status=&format=
 * Settings   GET/PATCH /attendance/settings/   { open_time, close_time, work_start, work_end, weekly_holiday }
 * Every action returns 403 without its permission (Settings → Users).
 */
export const attendanceApi = {
  getStatus: () => api.get('/attendance/status/'),
  checkIn: () => api.post('/attendance/check-in/'),
  checkOut: () => api.post('/attendance/check-out/'),
  listHistory: (params) => api.get('/attendance/history/', clean(params)),
  getOptions: () => api.get('/attendance/options/'),
  getDashboard: (params) => api.get('/attendance/dashboard/', clean(params)),

  listEmployees: (params) => api.get('/attendance/employees/', clean(params)),
  getEmployee: (id) => api.get(`/attendance/employees/${id}/`),
  createEmployee: (body) => api.post('/attendance/employees/', body),
  updateEmployee: (id, body) => api.patch(`/attendance/employees/${id}/`, body),
  deleteEmployee: (id) => api.delete(`/attendance/employees/${id}/`),

  listLeave: (params) => api.get('/attendance/leave/', clean(params)),
  createLeave: (body) => api.post('/attendance/leave/', body),
  updateLeave: (id, body) => api.patch(`/attendance/leave/${id}/`, body),
  leaveAction: (id, action) => api.post(`/attendance/leave/${id}/${action}/`),

  getCalendar: (params) => api.get('/attendance/calendar/', clean(params)),
  getReport: (params) => api.get('/attendance/reports/', clean(params)),
  downloadReport: (params) => api.download('/attendance/reports/', clean(params), `hipa-attendance-${params.type}.${params.format}`),

  listHolidays: (params) => api.get('/attendance/holidays/', clean(params)),
  createHoliday: (body) => api.post('/attendance/holidays/', body),
  updateHoliday: (id, body) => api.patch(`/attendance/holidays/${id}/`, body),
  deleteHoliday: (id) => api.delete(`/attendance/holidays/${id}/`),

  getSettings: () => api.get('/attendance/settings/'),
  updateSettings: (body) => api.patch('/attendance/settings/', body),
}
