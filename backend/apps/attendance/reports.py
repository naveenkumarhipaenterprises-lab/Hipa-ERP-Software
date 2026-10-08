"""Attendance reports in the existing report format ({title, table}), exported by services.exporters to PDF / Excel / CSV."""
from collections import Counter

from apps.reports.builders import col

from .models import LeaveRequest
from .services import ABSENT, DAY_LABELS, LEAVE, NOT_CHECKED_OUT, PERMISSION, PRESENT, days, duration_label, picture
from .window import IST

TYPES = {"daily": "Daily Attendance", "monthly": "Monthly Attendance", "employee": "Employee Attendance",
         "leave": "Leave / Permission Report"}


def clock(dt):
    return dt.astimezone(IST).strftime("%I:%M %p") if dt else None


def hhmm(t):
    return t.strftime("%I:%M %p") if t else None


def title(kind, start, end):
    return f"{TYPES[kind]} — {start:%d %b %Y}" + ("" if start == end else f" to {end:%d %b %Y}")


def build(kind, start, end, employees, status=None):
    if kind == "leave":
        return leave_report(start, end, employees, status)
    pic, _w = picture(employees, start, end)
    if kind == "monthly":
        return monthly(start, end, employees, pic, status)
    rows = []
    for d in days(start, end):
        for emp in employees:
            day = pic[emp.id].get(d)
            if not day or not day["statuses"] or (status and status not in day["statuses"]):
                continue
            rec = day["record"]
            rows.append({"date": d, "employee_code": emp.employee_code, "employee": emp.name, "department": emp.department or None,
                         "check_in": clock(rec.check_in_at) if rec else None, "check_out": clock(rec.check_out_at) if rec else None,
                         "duration": duration_label(rec.duration) if rec else None,
                         "status": ", ".join(DAY_LABELS[s] for s in day["statuses"])})
    return {"title": title(kind, start, end), "table": {
        "columns": [col("date", "Date", "date"), col("employee_code", "Employee ID"), col("employee", "Employee"),
                    col("department", "Department"), col("check_in", "Check-In"), col("check_out", "Check-Out"),
                    col("duration", "Working Duration"), col("status", "Status")],
        "rows": rows}}


def monthly(start, end, employees, pic, status):
    rows = []
    for emp in employees:
        counts, minutes = Counter(), 0
        for day in pic[emp.id].values():
            counts.update(day["statuses"])
            rec = day["record"]
            if rec and rec.duration:
                minutes += int(rec.duration.total_seconds() // 60)
        if status and not counts[status]:
            continue
        if not pic[emp.id]:
            continue
        rows.append({"employee_code": emp.employee_code, "employee": emp.name, "department": emp.department or None,
                     "present": counts[PRESENT], "not_checked_out": counts[NOT_CHECKED_OUT], "absent": counts[ABSENT],
                     "leave": counts[LEAVE], "permission": counts[PERMISSION],
                     "hours": f"{minutes // 60:02d}h {minutes % 60:02d}m"})
    return {"title": title("monthly", start, end), "table": {
        "columns": [col("employee_code", "Employee ID"), col("employee", "Employee"), col("department", "Department"),
                    col("present", "Present", align="right"), col("not_checked_out", "Not Checked Out", align="right"),
                    col("absent", "Absent", align="right"), col("leave", "Leave", align="right"),
                    col("permission", "Permission", align="right"), col("hours", "Working Hours", align="right")],
        "rows": rows}}


def leave_report(start, end, employees, status):
    qs = (LeaveRequest.objects.select_related("employee", "reviewed_by")
          .filter(employee__in=employees, date__range=(start, end)).order_by("date", "id"))
    if status:
        qs = qs.filter(status=status)
    rows = [{"requested": lr.created_at.astimezone(IST).date(), "date": lr.date, "employee_code": lr.employee.employee_code,
             "employee": lr.employee.name, "department": lr.employee.department or None, "type": lr.get_type_display(),
             "from": hhmm(lr.from_time), "to": hhmm(lr.to_time), "reason": lr.reason, "status": lr.get_status_display(),
             "reviewed_by": (lr.reviewed_by.name or lr.reviewed_by.username) if lr.reviewed_by else None} for lr in qs]
    return {"title": title("leave", start, end), "table": {
        "columns": [col("requested", "Request Date", "date"), col("date", "Date", "date"), col("employee_code", "Employee ID"),
                    col("employee", "Employee"), col("department", "Department"), col("type", "Type"), col("from", "From"),
                    col("to", "To"), col("reason", "Reason"), col("status", "Status"), col("reviewed_by", "Reviewed By")],
        "rows": rows}}
