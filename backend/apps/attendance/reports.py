"""Attendance reports in the existing report format ({title, table}), exported by services.exporters to PDF / Excel / CSV."""
from collections import Counter
from datetime import timedelta

from apps.reports.builders import col

from .models import LeaveRequest
from .services import (ABSENT, DAY_LABELS, LEAVE, NOT_CHECKED_OUT, OFFICE_HOLIDAY, PERMISSION, PRESENT, WEEKLY_HOLIDAY, days,
                       duration_label, picture)
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
    pic, _w, sched = picture(employees, start, end)
    if kind == "monthly":
        return monthly(start, end, employees, pic, status)
    rows = []
    for d in days(start, end):
        for emp in employees:
            day = pic[emp.id].get(d)
            if not day or not day["statuses"] or (status and status not in day["statuses"]):
                continue
            rec, f = day["record"], day["figures"]
            office = sched.holidays.get(d)
            rows.append({"date": d, "employee_code": emp.employee_code, "employee": emp.name, "department": emp.department or None,
                         "check_in": clock(rec.check_in_at) if rec else None, "check_out": clock(rec.check_out_at) if rec else None,
                         "scheduled": duration_label(f["scheduled"]), "total": duration_label(f["total"]), "permission": duration_label(f["permission"]),
                         "working": duration_label(f["working"]),
                         "status": ", ".join(DAY_LABELS[s] + (f" ({office.name})" if s == OFFICE_HOLIDAY and office else "")
                                             for s in day["statuses"])})
    return {"title": title(kind, start, end), "table": {
        "columns": [col("date", "Date", "date"), col("employee_code", "Employee ID"), col("employee", "Employee"),
                    col("department", "Department"), col("check_in", "Check-In"), col("check_out", "Check-Out"),
                    col("scheduled", "Scheduled Hours"), col("total", "Total Duration"), col("permission", "Approved Permission"), col("working", "Working Hours"),
                    col("status", "Status")],
        "rows": rows}}


def monthly(start, end, employees, pic, status):
    rows = []
    for emp in employees:
        counts, working, permission, scheduled = Counter(), timedelta(), timedelta(), timedelta()
        for day in pic[emp.id].values():
            counts.update(day["statuses"])
            scheduled += day["figures"]["scheduled"]
            if day["figures"]["working"] is not None:
                working += day["figures"]["working"]
                permission += day["figures"]["permission"]
        if status and not counts[status]:
            continue
        if not pic[emp.id]:
            continue
        rows.append({"employee_code": emp.employee_code, "employee": emp.name, "department": emp.department or None,
                     "working_days": len(pic[emp.id]) - counts[OFFICE_HOLIDAY] - counts[WEEKLY_HOLIDAY],
                     "present": counts[PRESENT], "not_checked_out": counts[NOT_CHECKED_OUT], "absent": counts[ABSENT],
                     "leave": counts[LEAVE], "permission": counts[PERMISSION], "office_holidays": counts[OFFICE_HOLIDAY],
                     "weekly_holidays": counts[WEEKLY_HOLIDAY], "scheduled_hours": duration_label(scheduled),
                     "permission_hours": duration_label(permission), "hours": duration_label(working)})
    return {"title": title("monthly", start, end), "table": {
        "columns": [col("employee_code", "Employee ID"), col("employee", "Employee"), col("department", "Department"),
                    col("working_days", "Working Days", align="right"), col("present", "Present", align="right"), col("not_checked_out", "Not Checked Out", align="right"),
                    col("absent", "Absent", align="right"), col("leave", "On Leave", align="right"),
                    col("permission", "Permission", align="right"), col("office_holidays", "Office Holidays", align="right"),
                    col("weekly_holidays", "Weekly Holidays", align="right"), col("scheduled_hours", "Scheduled Hours", align="right"),
                    col("permission_hours", "Approved Permission Hours", align="right"),
                    col("hours", "Working Hours", align="right")],
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
