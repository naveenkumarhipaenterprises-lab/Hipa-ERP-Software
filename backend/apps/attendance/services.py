"""Check-in / check-out, and the day-by-day attendance picture used by the calendar and the reports."""
from collections import defaultdict
from datetime import timedelta

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from . import permissions as perms
from . import window
from .models import AttendanceRecord, Employee, LeaveRequest

DAY = timedelta(days=1)

# Day statuses (calendar and reports)
PRESENT, NOT_CHECKED_OUT, ABSENT, LEAVE, PERMISSION = "present", "not_checked_out", "absent", "leave", "permission"
DAY_LABELS = {PRESENT: "Present", NOT_CHECKED_OUT: "Not checked out", ABSENT: "Absent", LEAVE: "Leave", PERMISSION: "Permission"}


def current_employees():
    return Employee.objects.filter(deleted_at__isnull=True)


def employee_of(user, lock=False):
    qs = current_employees().filter(user=user, status=Employee.Status.ACTIVE)
    return (qs.select_for_update() if lock else qs).first()


def require_employee(user, lock=False):
    emp = employee_of(user, lock)
    if emp is None:
        raise ValidationError({"detail": "Your login isn't linked to an active employee. "
                                         "Ask an administrator to link it in Attendance → Employees."})
    return emp


def duration_label(d):
    if d is None:
        return None
    minutes = int(d.total_seconds() // 60)
    return f"{minutes // 60:02d}h {minutes % 60:02d}m"


def is_not_checked_out(record, w):
    """Checked in, never checked out, and its window has closed."""
    return record.check_out_at is None and not (w.is_open and record.attendance_date == w.attendance_date)


def record_status(record, w):
    if record.check_out_at:
        return AttendanceRecord.Status.COMPLETED.label
    return DAY_LABELS[NOT_CHECKED_OUT] if is_not_checked_out(record, w) else AttendanceRecord.Status.CHECKED_IN.label


@transaction.atomic
def check_in(user):
    perms.require(user, "check_in", "You don't have permission to check in.")
    w = window.state()
    if not w.is_open:
        raise ValidationError({"detail": window.closed_message(w)})
    emp = require_employee(user, lock=True)
    if AttendanceRecord.objects.filter(employee=emp, attendance_date=w.attendance_date).exists():
        raise ValidationError({"detail": "You have already checked in for this attendance window."})
    try:
        with transaction.atomic():
            return AttendanceRecord.objects.create(employee=emp, attendance_date=w.attendance_date, check_in_at=window.now())
    except IntegrityError:
        raise ValidationError({"detail": "You have already checked in for this attendance window."})


@transaction.atomic
def check_out(user):
    perms.require(user, "check_out", "You don't have permission to check out.")
    w = window.state()
    if not w.is_open:
        raise ValidationError({"detail": window.closed_message(w)})
    emp = require_employee(user, lock=True)
    record = AttendanceRecord.objects.select_for_update().filter(employee=emp, attendance_date=w.attendance_date).first()
    if record is None:
        raise ValidationError({"detail": "You haven't checked in during this attendance window."})
    if record.check_out_at:
        raise ValidationError({"detail": "You have already checked out for this attendance window."})
    record.check_out_at = window.now()
    record.status = AttendanceRecord.Status.COMPLETED
    record.save(update_fields=["check_out_at", "status", "updated_at"])
    return record


# --- Day-by-day picture -------------------------------------------------------------------------

def employee_start(emp):
    return emp.joining_date or emp.created_at.astimezone(window.IST).date()


def employee_end(emp):
    return emp.deleted_at.astimezone(window.IST).date() if emp.deleted_at else None


def days(start, end):
    d = start
    while d <= end:
        yield d
        d += DAY


def picture(employees, start, end):
    """
    {employee_id: {date: {"statuses": [...], "record": AttendanceRecord|None, "leaves": [LeaveRequest]}}} for the
    days each employee was employed. Absent = a finished window with no check-in and no approved leave
    (only for active employees). Future days are left out. Three queries in total.
    """
    w = window.state()
    finished = window.last_finished_date(w)
    ids = [e.id for e in employees]
    records = {(r.employee_id, r.attendance_date): r
               for r in AttendanceRecord.objects.filter(employee_id__in=ids, attendance_date__range=(start, end))}
    leaves = defaultdict(list)
    for lr in LeaveRequest.objects.filter(employee_id__in=ids, date__range=(start, end), status=LeaveRequest.Status.APPROVED):
        leaves[(lr.employee_id, lr.date)].append(lr)
    out = {}
    for emp in employees:
        first, last = max(start, employee_start(emp)), min(end, w.last_date)
        if employee_end(emp):
            last = min(last, employee_end(emp))
        per_day = {}
        for d in days(first, last):
            rec, day_leaves = records.get((emp.id, d)), leaves.get((emp.id, d), [])
            statuses = []
            if rec:
                statuses.append(NOT_CHECKED_OUT if is_not_checked_out(rec, w) else PRESENT)
            if any(lr.type == LeaveRequest.Type.LEAVE for lr in day_leaves):
                statuses.append(LEAVE)
            if any(lr.type == LeaveRequest.Type.PERMISSION for lr in day_leaves):
                statuses.append(PERMISSION)
            if not statuses and d <= finished and emp.status == Employee.Status.ACTIVE:
                statuses.append(ABSENT)
            per_day[d] = {"statuses": statuses, "record": rec, "leaves": day_leaves}
        out[emp.id] = per_day
    return out, w
