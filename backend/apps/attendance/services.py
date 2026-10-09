"""
Check-in / check-out, holidays, scheduled and working hours, and the day-by-day attendance picture used by the
dashboard, calendar and reports. Every record belongs to a work day; see window.py for the timing rules.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from . import permissions as perms
from . import window
from .models import AttendanceRecord, AttendanceSettings, Employee, LeaveRequest, OfficeHoliday

DAY = timedelta(days=1)
ZERO = timedelta()

# Day statuses (dashboard, calendar and reports); each kept separate
PRESENT, NOT_CHECKED_OUT, ABSENT, LEAVE, PERMISSION = "present", "not_checked_out", "absent", "leave", "permission"
OFFICE_HOLIDAY, WEEKLY_HOLIDAY = "office_holiday", "weekly_holiday"
DAY_LABELS = {PRESENT: "Present", NOT_CHECKED_OUT: "Not checked out", ABSENT: "Absent", LEAVE: "On Leave",
              PERMISSION: "On Permission", OFFICE_HOLIDAY: "Office Holiday", WEEKLY_HOLIDAY: "Weekly Holiday"}


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
    """Checked in, never checked out, and its check-out time (until 09:20 AM the next morning) is over."""
    return record.check_out_at is None and not w.can_still_check_out(record)


def record_status(record, w):
    if record.check_out_at:
        return AttendanceRecord.Status.COMPLETED.label
    return DAY_LABELS[NOT_CHECKED_OUT] if is_not_checked_out(record, w) else AttendanceRecord.Status.CHECKED_IN.label


# --- Schedule: office hours and holidays -------------------------------------------------------------

@dataclass
class Schedule:
    """Office working hours, the weekly holiday and the office holidays of a date range."""

    settings: AttendanceSettings
    holidays: dict = field(default_factory=dict)  # {date: OfficeHoliday}

    def holiday(self, day):
        """OFFICE_HOLIDAY, WEEKLY_HOLIDAY or None. An office holiday on the weekly holiday counts once (as office)."""
        if day in self.holidays:
            return OFFICE_HOLIDAY
        if day.weekday() == self.settings.weekly_holiday:
            return WEEKLY_HOLIDAY
        return None

    def office_hours(self, day):
        return (datetime.combine(day, self.settings.work_start, tzinfo=window.IST),
                datetime.combine(day, self.settings.work_end, tzinfo=window.IST))

    def scheduled(self, day):
        """Scheduled working hours of a day: the office hours, or nothing on a holiday."""
        if self.holiday(day):
            return ZERO
        start, end = self.office_hours(day)
        return end - start


def schedule_for(days, settings=None):
    """A Schedule with the office holidays on the given dates (one query)."""
    days = {d for d in days if d}
    holidays = {h.date: h for h in OfficeHoliday.objects.filter(date__in=days)} if days else {}
    return Schedule(settings or AttendanceSettings.load(), holidays)


def schedule_between(start, end, settings=None):
    return Schedule(settings or AttendanceSettings.load(), {h.date: h for h in OfficeHoliday.objects.filter(date__range=(start, end))})


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


def figures(record, permissions, schedule, day=None):
    """
    Scheduled hours (office hours; nothing on a holiday), total time checked in, approved permission that overlaps
    both the office hours and the time checked in, and actual working hours (total − that permission).
    Pending, rejected and cancelled requests never count; overlapping requests count once. Worked out when shown,
    so approving, editing or cancelling a request updates them. Total/permission/working are None until checked out.
    """
    day = day or (record.attendance_date if record else None)
    out = {"scheduled": schedule.scheduled(day) if day else None, "total": None, "permission": None, "working": None}
    if record is None or record.check_out_at is None:
        return out
    start, end = record.check_in_at, record.check_out_at
    office_start, office_end = schedule.office_hours(record.attendance_date)
    spans = []
    if not schedule.holiday(record.attendance_date):
        for lr in permissions:
            if lr.status != LeaveRequest.Status.APPROVED or lr.type != LeaveRequest.Type.PERMISSION or not lr.from_time or not lr.to_time:
                continue
            a = max(start, office_start, datetime.combine(lr.date, lr.from_time, tzinfo=window.IST))
            b = min(end, office_end, datetime.combine(lr.date, lr.to_time, tzinfo=window.IST))
            if b > a:
                spans.append((a, b))
    covered = ZERO
    for a, b in _merge(sorted(spans)):
        covered += b - a
    total = end - start
    out.update(total=total, permission=covered, working=total - covered)
    return out


def _merge(spans):
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


# --- Check-in / check-out ----------------------------------------------------------------------

def open_record(emp, w, lock=False):
    """The employee's record that can be checked out now (the oldest still open), or None."""
    qs = AttendanceRecord.objects.filter(employee=emp, check_out_at__isnull=True,
                                         attendance_date__gte=w.at.date() - DAY).order_by("attendance_date")
    if lock:
        qs = qs.select_for_update()
    return next((r for r in qs if w.can_still_check_out(r)), None)


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
    """Allowed at any time (also while Check-In is closed) for an open record, until 09:20 AM the next morning."""
    perms.require(user, "check_out", "You don't have permission to check out.")
    w = window.state()
    emp = require_employee(user, lock=True)
    record = open_record(emp, w, lock=True)
    if record is None:
        raise ValidationError({"detail": "You have no open check-in to check out."})
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
    {employee_id: {work day: {"statuses": [...], "record", "leaves", "figures"}}} for the days each employee was
    employed, plus the Window and Schedule used. Absent = no check-in by the check-in deadline on a working day, with
    no approved leave or permission (active employees only); weekly and office holidays are never absent. Days still
    to come are left out. Four queries in total.
    """
    w = window.state()
    today = w.at.date()
    finished = window.finished_date(w)
    last_day = max(today, w.checkin_date) if w.is_open else today
    sched = schedule_between(start, end)
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
            holiday = sched.holiday(d)
            statuses = []
            if rec:
                statuses.append(NOT_CHECKED_OUT if is_not_checked_out(rec, w) else PRESENT)
            if any(lr.type == LeaveRequest.Type.LEAVE for lr in day_leaves):
                statuses.append(LEAVE)
            if any(lr.type == LeaveRequest.Type.PERMISSION for lr in day_leaves):
                statuses.append(PERMISSION)
            if holiday:
                statuses.append(holiday)
            elif not statuses and d <= finished and emp.status == Employee.Status.ACTIVE:
                statuses.append(ABSENT)
            per_day[d] = {"statuses": statuses, "record": rec, "leaves": day_leaves,
                          "holiday": sched.holidays.get(d), "figures": figures(rec, day_leaves, sched, d)}
        out[emp.id] = per_day
    return out, w, sched
