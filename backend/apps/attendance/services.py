"""
Check-in / check-out, working hours, and the day-by-day attendance picture used by the calendar and the reports.
Every record belongs to a work day (09:00 AM – 05:30 PM); see window.py for when each action is allowed.
"""
from collections import defaultdict
from datetime import datetime, timedelta

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
    """Checked in, never checked out, and the time to check out for that work day is over."""
    return record.check_out_at is None and record.attendance_date < window.checkout_open_from(w)


def record_status(record, w):
    if record.check_out_at:
        return AttendanceRecord.Status.COMPLETED.label
    return DAY_LABELS[NOT_CHECKED_OUT] if is_not_checked_out(record, w) else AttendanceRecord.Status.CHECKED_IN.label


# --- Working hours ------------------------------------------------------------------------------

def approved_permissions(records):
    """{(employee_id, work day): [approved permission requests]} for these records, in one query."""
    keys = {(r.employee_id, r.attendance_date) for r in records}
    out = defaultdict(list)
    if not keys:
        return out
    qs = LeaveRequest.objects.filter(type=LeaveRequest.Type.PERMISSION, status=LeaveRequest.Status.APPROVED,
                                     employee_id__in={k[0] for k in keys}, date__in={k[1] for k in keys})
    for lr in qs:
        if (lr.employee_id, lr.date) in keys:
            out[(lr.employee_id, lr.date)].append(lr)
    return out


def figures(record, permissions):
    """
    Total time (check-in → check-out), the part of it covered by APPROVED permission, and the actual working hours
    (total − permission). Pending, rejected and cancelled requests never count. None until checked out.
    """
    if record is None or record.check_out_at is None:
        return {"total": None, "permission": None, "working": None}
    start, end = record.check_in_at, record.check_out_at
    spans = []
    for lr in permissions:
        if lr.status != LeaveRequest.Status.APPROVED or lr.type != LeaveRequest.Type.PERMISSION or not lr.from_time or not lr.to_time:
            continue
        a = max(start, datetime.combine(lr.date, lr.from_time, tzinfo=window.IST))
        b = min(end, datetime.combine(lr.date, lr.to_time, tzinfo=window.IST))
        if b > a:
            spans.append((a, b))
    covered = timedelta()
    for a, b in _merge(sorted(spans)):  # overlapping requests are counted once
        covered += b - a
    total = end - start
    return {"total": total, "permission": covered, "working": total - covered}


def _merge(spans):
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


# --- Check-in / check-out ----------------------------------------------------------------------

@transaction.atomic
def check_in(user):
    perms.require(user, "check_in", "You don't have permission to check in.")
    w = window.state()
    if not w.is_open:
        raise ValidationError({"detail": window.closed_message(w)})
    emp = require_employee(user, lock=True)
    taken = f"You have already checked in for {w.checkin_date:%d %b %Y}."
    if AttendanceRecord.objects.filter(employee=emp, attendance_date=w.checkin_date).exists():
        raise ValidationError({"detail": taken})
    try:
        with transaction.atomic():
            return AttendanceRecord.objects.create(employee=emp, attendance_date=w.checkin_date, check_in_at=window.now())
    except IntegrityError:
        raise ValidationError({"detail": taken})


@transaction.atomic
def check_out(user):
    perms.require(user, "check_out", "You don't have permission to check out.")
    w = window.state()
    if not w.is_open:
        raise ValidationError({"detail": window.closed_message(w)})
    emp = require_employee(user, lock=True)
    record = AttendanceRecord.objects.select_for_update().filter(employee=emp, attendance_date=w.checkout_date).first()
    if record is None:
        raise ValidationError({"detail": f"You haven't checked in for {w.checkout_date:%d %b %Y}."})
    if record.check_out_at:
        raise ValidationError({"detail": f"You have already checked out for {w.checkout_date:%d %b %Y}."})
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
    {employee_id: {work day: {"statuses": [...], "record": AttendanceRecord|None, "leaves": [LeaveRequest],
    "figures": {...}}}} for the days each employee was employed. Absent = no check-in by the check-in deadline and no
    approved leave (active employees only). Days still to come are left out. Three queries in total.
    """
    w = window.state()
    today = window.now().date()
    finished = window.finished_date(w)
    last_day = max(today, w.checkin_date) if w.is_open else today
    ids = [e.id for e in employees]
    records = {(r.employee_id, r.attendance_date): r
               for r in AttendanceRecord.objects.filter(employee_id__in=ids, attendance_date__range=(start, end))}
    leaves = defaultdict(list)
    for lr in LeaveRequest.objects.filter(employee_id__in=ids, date__range=(start, end), status=LeaveRequest.Status.APPROVED):
        leaves[(lr.employee_id, lr.date)].append(lr)
    out = {}
    for emp in employees:
        first, last = max(start, employee_start(emp)), min(end, last_day)
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
            per_day[d] = {"statuses": statuses, "record": rec, "leaves": day_leaves, "figures": figures(rec, day_leaves)}
        out[emp.id] = per_day
    return out, w
