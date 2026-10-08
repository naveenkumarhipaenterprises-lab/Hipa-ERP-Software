import { api, cleanParams as clean } from './client'

/**
 * Attendance endpoints (Django REST API). The server decides everything time-related: whether the window is open,
 * and every check-in / check-out time. Nothing time-related is ever sent from the browser.
 *
 * GET  /attendance/status/     -> { server_time, timezone, window: { is_open, checkin_date, checkout_date, opens_at, closes_at,
 *                                   open_time, close_time, work_start, work_end, message }, employee, work_date, record,
 *                                   can_check_in, check_in_for, can_check_out, permissions }
 *      record: { attendance_date (the work day), check_in_at, check_out_at, total_duration, permission_duration,
 *                working_duration, status }   // working = total − approved permission inside it
 * POST /attendance/check-in/   -> status            POST /attendance/check-out/  -> status
 * GET  /attendance/history/    -> own records        GET /attendance/records/   -> everyone's (reports permission)
 * GET  /attendance/options/    -> { permissions, leave_types, leave_statuses, employee_statuses, day_statuses, report_types,
 *                                   departments, employees, users }
 * Employees  GET/POST /attendance/employees/  ·  GET/PATCH/DELETE /attendance/employees/<id>/   (delete keeps history)
 * Leave      GET/POST /attendance/leave/?scope=all&status=  ·  PATCH /attendance/leave/<id>/  ·  POST .../<id>/approve|reject|cancel/
 * Calendar   GET /attendance/calendar/?month=YYYY-MM&employee=
 * Reports    GET /attendance/reports/?type=daily|monthly|employee|leave&date_from=&date_to=&employee=&department=&status=&format=
 * Settings   GET/PATCH /attendance/settings/   { open_time, close_time }
 * Every action returns 403 without its permission (Settings → Users).
 */
export const attendanceApi = {
  getStatus: () => api.get('/attendance/status/'),
  checkIn: () => api.post('/attendance/check-in/'),
  checkOut: () => api.post('/attendance/check-out/'),
  listHistory: (params) => api.get('/attendance/history/', clean(params)),
  getOptions: () => api.get('/attendance/options/'),

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

  getSettings: () => api.get('/attendance/settings/'),
  updateSettings: (body) => api.patch('/attendance/settings/', body),
}
