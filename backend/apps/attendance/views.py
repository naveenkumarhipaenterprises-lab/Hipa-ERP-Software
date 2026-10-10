"""
Attendance API. Every signed-in user can open the module; each action checks its own per-user permission
(permissions.py) on the server. Check-in needs the Check-In window to be open; check-out works at any time for an
open record until 09:20 AM the next morning (window.py).
"""
import re
from calendar import monthrange
from datetime import date, datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core import parsing
from apps.core.views import ModuleAPIView
from services import audit
from services.exporters import MIME, export

from . import permissions as perms
from . import reports, services, window
from .models import WEEKDAYS, AttendanceRecord, AttendanceSettings, Employee, LeaveRequest, OfficeHoliday
from .services import (ABSENT, DAY_LABELS, LEAVE, OFFICE_HOLIDAY, approved_permissions, current_employees, duration_label,
                       employee_of, figures, record_status, schedule_for)

LS = LeaveRequest.Status
MAX_REPORT_DAYS = 93


class AttendanceView(ModuleAPIView):
    module = "attendance"


# --- Rows ---------------------------------------------------------------------------------------

def iso(dt):
    return dt.astimezone(window.IST).isoformat() if dt else None


def employee_brief(e):
    return {"id": e.id, "employee_code": e.employee_code, "name": e.name, "department": e.department or None}


def employee_row(e):
    return {**employee_brief(e), "designation": e.designation or None, "email": e.email or None, "phone": e.phone or None,
            "joining_date": e.joining_date, "status": e.get_status_display(), "status_value": e.status,
            "user": {"id": e.user_id, "name": e.user.name or e.user.username, "email": e.user.email} if e.user_id else None}


def figures_block(f):
    """Scheduled hours, total time, approved permission deducted, and actual working hours (total − permission)."""
    return {"scheduled_duration": duration_label(f["scheduled"]), "total_duration": duration_label(f["total"]),
            "permission_duration": duration_label(f["permission"]), "working_duration": duration_label(f["working"])}


def holiday_block(sched, day):
    """{"type", "label", "name", "description"} when the day is an office or the weekly holiday, else None."""
    kind = sched.holiday(day)
    if not kind:
        return None
    h = sched.holidays.get(day) if kind == OFFICE_HOLIDAY else None
    return {"type": kind, "label": DAY_LABELS[kind], "name": h.name if h else dict(WEEKDAYS)[day.weekday()],
            "description": (h.description or None) if h else None}


def record_row(r, w, sched, permissions=()):
    return {"id": r.id, "attendance_date": r.attendance_date, "employee": employee_brief(r.employee),
            "check_in_at": iso(r.check_in_at), "check_out_at": iso(r.check_out_at),
            **figures_block(figures(r, permissions, sched)), "holiday": holiday_block(sched, r.attendance_date),
            "status": record_status(r, w)}


def record_rows(records, w):
    """Rows for a page of records, with their approved permissions and office holidays fetched in one query each."""
    records = list(records)
    found = approved_permissions(records)
    sched = schedule_for(r.attendance_date for r in records)
    return [record_row(r, w, sched, found.get((r.employee_id, r.attendance_date), [])) for r in records]


def permission_times(leaves):
    return [f"{window.clock(lr.from_time)} – {window.clock(lr.to_time)}" for lr in leaves
            if lr.type == LeaveRequest.Type.PERMISSION and lr.from_time and lr.to_time]


def leave_row(lr, user):
    mine = lr.requested_by_id == user.id or (lr.employee.user_id == user.id)
    pending = lr.status == LS.PENDING
    return {"id": lr.id, "employee": employee_brief(lr.employee), "type": lr.get_type_display(), "type_value": lr.type,
            "date": lr.date, "from_time": lr.from_time.strftime("%H:%M") if lr.from_time else None,
            "to_time": lr.to_time.strftime("%H:%M") if lr.to_time else None, "reason": lr.reason, "remarks": lr.remarks or None,
            "status": lr.get_status_display(), "requested_at": iso(lr.created_at),
            "reviewed_by": (lr.reviewed_by.name or lr.reviewed_by.username) if lr.reviewed_by else None,
            "reviewed_at": iso(lr.reviewed_at),
            "can_edit": mine and pending, "can_cancel": mine and pending,
            "can_approve": pending and perms.has(user, "leave_approve"), "can_reject": pending and perms.has(user, "leave_reject")}


def window_block(w, s):
    return {"is_open": w.is_open, "checkin_date": w.checkin_date,
            "opens_at": iso(w.opens_at), "closes_at": iso(w.closes_at),
            "open_time": s.open_time.strftime("%H:%M"), "close_time": s.close_time.strftime("%H:%M"),
            "work_start": s.work_start.strftime("%H:%M"), "work_end": s.work_end.strftime("%H:%M"),
            "weekly_holiday": dict(WEEKDAYS)[s.weekly_holiday],
            "message": None if w.is_open else window.closed_message(w)}


# --- Attendance ------------------------------------------------------------------------------------

def status_payload(user):
    s = AttendanceSettings.load()
    w = window.state(settings=s)
    emp = employee_of(user)
    today = w.at.date()
    flags = perms.flags(user)
    to_close = services.open_record(emp, w) if emp else None
    taken = bool(emp and w.is_open and AttendanceRecord.objects.filter(employee=emp, attendance_date=w.checkin_date).exists())
    can_in = bool(w.is_open and emp and not taken)  # no permission needed: own attendance only
    can_out = bool(to_close)
    # The work day to show: the one still open, otherwise today's
    record = to_close or (AttendanceRecord.objects.filter(employee=emp, attendance_date=today).first() if emp else None)
    work_date = record.attendance_date if record else today
    sched = schedule_for([work_date], s)
    office_start, office_end = sched.office_hours(work_date)
    return {
        "server_time": iso(w.at),
        "timezone": "Asia/Kolkata (IST)",
        "window": window_block(w, s),
        "employee": employee_brief(emp) if emp else None,
        "work_date": work_date,
        "office_hours": f"{window.clock(office_start)} – {window.clock(office_end)}",
        "scheduled_duration": duration_label(sched.scheduled(work_date)),
        "holiday": holiday_block(sched, work_date),
        "record": record_rows([record], w)[0] if record else None,
        "can_check_in": can_in,
        "check_in_for": w.checkin_date if w.is_open else None,
        "can_check_out": can_out,
        "checkout_until": iso(w.checkout_deadline(to_close.attendance_date)) if to_close else None,
        "permissions": flags,
    }


class StatusView(AttendanceView):
    def get(self, request):
        return Response(status_payload(request.user))


class CheckInView(AttendanceView):
    def post(self, request):
        services.check_in(request.user)  # the time is the server's; nothing from the request is used
        return Response(status_payload(request.user), status=status.HTTP_201_CREATED)


class CheckOutView(AttendanceView):
    def post(self, request):
        services.check_out(request.user)
        return Response(status_payload(request.user))


class HistoryView(AttendanceView):
    """The signed-in employee's own attendance, newest first."""

    def get(self, request):
        emp = employee_of(request.user)
        qs = AttendanceRecord.objects.select_related("employee").filter(employee=emp) if emp else AttendanceRecord.objects.none()
        return self.get_paginated_response(record_rows(self.paginate_queryset(qs), window.state()))


class RecordsView(AttendanceView):
    """Everyone's attendance records (needs the reports permission)."""

    def get(self, request):
        perms.require(request.user, "report_view", "You don't have permission to view everyone's attendance.")
        qs = AttendanceRecord.objects.select_related("employee")
        start, end = optional_date(self.param("date_from"), "date_from"), optional_date(self.param("date_to"), "date_to")
        if start:
            qs = qs.filter(attendance_date__gte=start)
        if end:
            qs = qs.filter(attendance_date__lte=end)
        emp = self.int_param("employee")
        if emp:
            qs = qs.filter(employee_id=emp)
        if self.param("department"):
            qs = qs.filter(employee__department__iexact=self.param("department"))
        return self.get_paginated_response(record_rows(self.paginate_queryset(qs), window.state()))


class OptionsView(AttendanceView):
    def get(self, request):
        user, flags = request.user, perms.flags(request.user)
        data = {
            "permissions": flags,
            "leave_types": [{"value": v, "label": l} for v, l in LeaveRequest.Type.choices],
            "leave_statuses": [{"value": v, "label": l} for v, l in LS.choices],
            "employee_statuses": [{"value": v, "label": l} for v, l in Employee.Status.choices],
            "day_statuses": [{"value": v, "label": l} for v, l in DAY_LABELS.items()],
            "report_types": [{"value": v, "label": l} for v, l in reports.TYPES.items()],
        "weekdays": [{"value": v, "label": l} for v, l in WEEKDAYS],
            "departments": sorted({d for d in current_employees().exclude(department="").values_list("department", flat=True)}),
            "employees": [],
            "users": [],
        }
        if any(flags[c] for c in ("view_all", "employee_view", "employee_manage", "leave_view", "calendar_view", "report_view")):
            data["employees"] = [employee_brief(e) for e in current_employees()]
        if flags["employee_manage"]:
            linked = current_employees().exclude(user=None).values_list("user_id", flat=True)
            data["users"] = [{"id": u.id, "name": u.name or u.username, "email": u.email}
                             for u in User.objects.filter(is_active=True).exclude(id__in=list(linked)).order_by("name")]
        return Response(data)


# --- Employees ----------------------------------------------------------------------------------

PHONE = re.compile(r"^[0-9+\-() ]{6,20}$")


def read_employee(d, current=None):
    errors = {}
    code = parsing.text(d, "employee_code", 30, required=True, errors=errors, label="employee ID")
    name = parsing.text(d, "name", 150, required=True, errors=errors, label="employee name")
    email = parsing.text(d, "email", 254).lower()
    if email:
        try:
            validate_email(email)
        except DjangoValidationError:
            errors["email"] = ["Enter a valid e-mail address."]
    phone = parsing.text(d, "phone", 20)
    if phone and not PHONE.match(phone):
        errors["phone"] = ["Enter a valid phone number."]
    joining = parsing.date(d, "joining_date", errors, required=False, label="joining date")
    st = parsing.choice(d, "status", Employee.Status, errors, default=Employee.Status.ACTIVE)
    user = parsing.record(d, "user_id", User.objects.filter(is_active=True), errors, required=False, message="Choose an active portal user.")
    if code and current_employees().filter(employee_code__iexact=code).exclude(pk=current.pk if current else None).exists():
        errors["employee_code"] = [f"Employee ID {code} is already used."]
    if user and current_employees().filter(user=user).exclude(pk=current.pk if current else None).exists():
        errors["user_id"] = ["This login is already linked to another employee."]
    if errors:
        raise ValidationError(errors)
    return {"employee_code": code, "name": name, "department": parsing.text(d, "department", 100),
            "designation": parsing.text(d, "designation", 100), "email": email, "phone": phone,
            "joining_date": joining, "status": st, "user": user}


def employees_qs():
    return current_employees().select_related("user")


class EmployeesView(AttendanceView):
    def get(self, request):
        perms.require_any(request.user, ("employee_view", "employee_manage"), "You don't have permission to view employees.")
        qs = employees_qs()
        q = self.param("search")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(employee_code__icontains=q) | Q(department__icontains=q) | Q(email__icontains=q))
        st = self.param("status")
        if st:
            if st not in Employee.Status.values:
                raise ValidationError({"status": ["Use active or inactive."]})
            qs = qs.filter(status=st)
        if self.param("department"):
            qs = qs.filter(department__iexact=self.param("department"))
        return self.paginated(qs, employee_row)

    def post(self, request):
        perms.require(request.user, "employee_manage", "You don't have permission to manage employees.")
        e = Employee.objects.create(**read_employee(request.data))
        audit.record(request, "Added employee", f"{e.employee_code} {e.name}")
        return Response(employee_row(e), status=status.HTTP_201_CREATED)


class EmployeeDetailView(AttendanceView):
    def get(self, request, pk):
        perms.require_any(request.user, ("employee_view", "employee_manage"), "You don't have permission to view employees.")
        return Response(employee_row(get_object_or_404(employees_qs(), pk=pk)))

    def patch(self, request, pk):
        perms.require(request.user, "employee_manage", "You don't have permission to manage employees.")
        e = get_object_or_404(employees_qs(), pk=pk)
        current = {"employee_code": e.employee_code, "name": e.name, "department": e.department, "designation": e.designation,
                   "email": e.email, "phone": e.phone, "joining_date": e.joining_date.isoformat() if e.joining_date else "",
                   "status": e.status, "user_id": e.user_id or ""}
        fields = read_employee({**current, **{k: request.data.get(k) for k in current if k in request.data}}, current=e)
        for k, v in fields.items():
            setattr(e, k, v)
        e.save()
        audit.record(request, "Edited employee", f"{e.employee_code} {e.name}")
        return Response(employee_row(e))

    def delete(self, request, pk):
        """Removes the employee from the list and unlinks their login; attendance and leave history are kept."""
        perms.require(request.user, "employee_manage", "You don't have permission to manage employees.")
        e = get_object_or_404(employees_qs(), pk=pk)
        e.deleted_at, e.status, e.user = timezone.now(), Employee.Status.INACTIVE, None
        e.save(update_fields=["deleted_at", "status", "user", "updated_at"])
        audit.record(request, "Deleted employee", f"{e.employee_code} {e.name}")
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Leave / Permission ----------------------------------------------------------------------------

def optional_date(raw, name):
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValidationError({name: ["Use YYYY-MM-DD."]})


def read_time(d, name, errors):
    raw = str(d.get(name) or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:5], "%H:%M").time()
    except ValueError:
        errors[name] = ["Enter a time (HH:MM)."]
        return None


def read_leave(d):
    errors = {}
    kind = parsing.choice(d, "type", LeaveRequest.Type, errors, message="Choose Leave or Permission.")
    day = parsing.date(d, "date", errors)
    start, end = read_time(d, "from_time", errors), read_time(d, "to_time", errors)
    reason = parsing.text(d, "reason", 255, required=True, errors=errors, label="reason")
    if kind == LeaveRequest.Type.PERMISSION:
        if not start and "from_time" not in errors:
            errors["from_time"] = ["Enter the from time."]
        if not end and "to_time" not in errors:
            errors["to_time"] = ["Enter the to time."]
    elif bool(start) != bool(end) and not errors.get("from_time") and not errors.get("to_time"):
        errors["to_time" if start else "from_time"] = ["Enter both times, or leave both empty for a whole day."]
    if start and end and end <= start:
        errors["to_time"] = ["The to time must be after the from time."]
    if errors:
        raise ValidationError(errors)
    return {"type": kind, "date": day, "from_time": start, "to_time": end, "reason": reason,
            "remarks": parsing.text(d, "remarks", 2000)}


def leave_qs():
    return LeaveRequest.objects.select_related("employee", "reviewed_by")


class LeaveView(AttendanceView):
    """Own requests by default; ?scope=all lists everyone's (needs the leave view permission)."""

    def get(self, request):
        user = request.user
        if self.param("scope") == "all":
            perms.require(user, "leave_view", "You don't have permission to view everyone's requests.")
            qs = leave_qs()
            emp = self.int_param("employee")
            if emp:
                qs = qs.filter(employee_id=emp)
        else:
            qs = leave_qs().filter(Q(employee__user=user) | Q(requested_by=user))
        q = self.param("search")
        if q:
            qs = qs.filter(Q(reason__icontains=q) | Q(remarks__icontains=q) | Q(employee__name__icontains=q)
                           | Q(employee__employee_code__icontains=q))
        st = self.param("status")
        if st:
            if st not in LS.values:
                raise ValidationError({"status": ["Unknown status."]})
            qs = qs.filter(status=st)
        kind = self.param("type")
        if kind:
            qs = qs.filter(type=kind)
        return self.paginated(qs, lambda lr: leave_row(lr, user))

    def post(self, request):
        perms.require(request.user, "leave_apply", "You don't have permission to apply for leave or permission.")
        emp = services.require_employee(request.user)
        lr = LeaveRequest.objects.create(employee=emp, requested_by=request.user, **read_leave(request.data))
        audit.record(request, f"Requested {lr.get_type_display().lower()}", f"{emp.name} {lr.date:%d %b %Y}")
        return Response(leave_row(lr, request.user), status=status.HTTP_201_CREATED)


class LeaveDetailView(AttendanceView):
    def patch(self, request, pk):
        lr = get_object_or_404(leave_qs(), pk=pk)
        if not (lr.requested_by_id == request.user.id or lr.employee.user_id == request.user.id):
            raise PermissionDenied("You can only change your own requests.")
        if lr.status != LS.PENDING:
            raise ValidationError({"detail": f"A {lr.get_status_display().lower()} request can't be changed."})
        current = {"type": lr.type, "date": lr.date.isoformat(), "from_time": lr.from_time.strftime("%H:%M") if lr.from_time else "",
                   "to_time": lr.to_time.strftime("%H:%M") if lr.to_time else "", "reason": lr.reason, "remarks": lr.remarks}
        for k, v in read_leave({**current, **{k: request.data.get(k) for k in current if k in request.data}}).items():
            setattr(lr, k, v)
        lr.save()
        return Response(leave_row(lr, request.user))


class LeaveActionView(AttendanceView):
    """POST approve | reject (by permission) or cancel (own pending request)."""

    ACTIONS = {"approve": (LS.APPROVED, "leave_approve"), "reject": (LS.REJECTED, "leave_reject"), "cancel": (LS.CANCELLED, None)}

    def post(self, request, pk, action):
        new, code = self.ACTIONS[action]
        with transaction.atomic():
            lr = get_object_or_404(leave_qs().select_for_update(of=("self",)), pk=pk)
            if code:
                perms.require(request.user, code, f"You don't have permission to {action} requests.")
            elif not (lr.requested_by_id == request.user.id or lr.employee.user_id == request.user.id):
                raise PermissionDenied("You can only cancel your own requests.")
            if lr.status != LS.PENDING:
                raise ValidationError({"detail": f"This request is already {lr.get_status_display().lower()}."})
            lr.status = new
            if code:
                lr.reviewed_by, lr.reviewed_at = request.user, timezone.now()
            lr.save()
        audit.record(request, f"{lr.get_status_display()} {lr.get_type_display().lower()} request", f"{lr.employee.name} {lr.date:%d %b %Y}")
        return Response(leave_row(lr, request.user))


# --- Calendar -----------------------------------------------------------------------------------

class CalendarView(AttendanceView):
    """?month=YYYY-MM&employee=<id>. Own calendar by default; another employee's needs the calendar permission."""

    def get(self, request):
        raw = self.param("month") or f"{window.now():%Y-%m}"
        if not re.fullmatch(r"\d{4}-\d{2}", raw) or not 1 <= int(raw[5:]) <= 12:
            raise ValidationError({"month": ["Use YYYY-MM."]})
        year, month = int(raw[:4]), int(raw[5:])
        start, end = date(year, month, 1), date(year, month, monthrange(year, month)[1])
        wanted = self.int_param("employee")
        own = employee_of(request.user)
        if wanted and (not own or wanted != own.id):
            perms.require(request.user, "calendar_view", "You don't have permission to view other employees' calendars.")
            emp = get_object_or_404(Employee, pk=wanted)
        else:
            emp = own
        if emp is None:
            pic, sched = {}, services.schedule_between(start, end)
        else:
            found, _w, sched = services.picture([emp], start, end)
            pic = found[emp.id]
        out = []
        for d in services.days(start, end):
            day = pic.get(d)
            if day is None:  # days still to come (or before joining) show only their holiday
                if not sched.holiday(d):
                    continue
                day = {"statuses": [sched.holiday(d)], "record": None, "leaves": [], "figures": figures(None, [], sched, d)}
            rec = day["record"]
            out.append({"date": d, "statuses": day["statuses"], "labels": [DAY_LABELS[s] for s in day["statuses"]],
                        "holiday": holiday_block(sched, d),
                        "check_in_at": iso(rec.check_in_at) if rec else None, "check_out_at": iso(rec.check_out_at) if rec else None,
                        **figures_block(day["figures"]),
                        "leaves": [{"type": lr.get_type_display(), "from_time": lr.from_time.strftime("%H:%M") if lr.from_time else None,
                                    "to_time": lr.to_time.strftime("%H:%M") if lr.to_time else None, "reason": lr.reason}
                                   for lr in day["leaves"]]})
        return Response({"month": raw, "employee": employee_brief(emp) if emp else None, "days": out,
                         "holidays": [holiday_row(h) for h in sorted(sched.holidays.values(), key=lambda h: h.date)]})


# --- Reports ------------------------------------------------------------------------------------

class ReportView(AttendanceView):
    """?type=daily|monthly|employee|leave&date_from=&date_to=&employee=&department=&status=&format=json|pdf|xlsx|csv"""

    def get(self, request):
        perms.require(request.user, "report_view", "You don't have permission to view attendance reports.")
        kind = self.param("type") or "daily"
        if kind not in reports.TYPES:
            raise ValidationError({"type": [f"Use one of: {', '.join(reports.TYPES)}."]})
        today = window.now().date()
        start = optional_date(self.param("date_from"), "date_from") or today.replace(day=1)
        end = optional_date(self.param("date_to"), "date_to") or today
        if end < start:
            raise ValidationError({"date_to": ["The end date can't be before the start date."]})
        if kind != "leave" and (end - start).days >= MAX_REPORT_DAYS:
            raise ValidationError({"date_to": [f"Choose at most {MAX_REPORT_DAYS} days."]})
        employees = Employee.objects.all()  # deleted employees still appear for the days they worked
        emp_id = self.int_param("employee")
        if kind == "employee" and not emp_id:
            raise ValidationError({"employee": ["Choose an employee."]})
        if emp_id:
            employees = employees.filter(pk=emp_id)
        if self.param("department"):
            employees = employees.filter(department__iexact=self.param("department"))
        st = self.param("status") or None
        allowed = LS.values if kind == "leave" else list(DAY_LABELS)
        if st and st not in allowed:
            raise ValidationError({"status": ["Unknown status for this report."]})
        data = reports.build(kind, start, end, list(employees), st)
        fmt = self.param("format") or "json"
        if fmt == "json":
            return Response(data)
        if fmt not in MIME:
            raise ValidationError({"format": ["Use json, pdf, xlsx or csv."]})
        perms.require(request.user, "report_export", "You don't have permission to export attendance reports.")
        content, mime = export(data, fmt)
        response = HttpResponse(content, content_type=mime)
        response["Content-Disposition"] = f'attachment; filename="hipa-attendance-{kind}-{start:%Y%m%d}-{end:%Y%m%d}.{fmt}"'
        audit.record(request, "Exported attendance report", f"{kind} {start} – {end} {fmt}")
        return response


# --- Settings -----------------------------------------------------------------------------------

SETTING_TIMES = {"open_time": "open time", "close_time": "close time", "work_start": "working hours start",
                 "work_end": "working hours end"}


def settings_payload(s):
    start, end = (datetime.combine(date.min, t) for t in (s.work_start, s.work_end))
    return {**{name: getattr(s, name).strftime("%H:%M") for name in SETTING_TIMES},
            "weekly_holiday": s.weekly_holiday, "weekly_holiday_label": dict(WEEKDAYS)[s.weekly_holiday],
            "scheduled_duration": duration_label(end - start),
            "timezone": "Asia/Kolkata (IST)", "updated_at": iso(s.updated_at)}


class SettingsView(AttendanceView):
    def get(self, request):
        perms.require_any(request.user, ("settings_view", "settings_manage"), "You don't have permission to view attendance settings.")
        return Response(settings_payload(AttendanceSettings.load()))

    def patch(self, request):
        perms.require(request.user, "settings_manage", "You don't have permission to change attendance settings.")
        s = AttendanceSettings.load()
        errors, values = {}, {}
        for name, label in SETTING_TIMES.items():
            values[name] = read_time(request.data, name, errors) if name in request.data else getattr(s, name)
            if values[name] is None and name not in errors:
                errors[name] = [f"Enter the {label}."]
        weekly = str(request.data.get("weekly_holiday", s.weekly_holiday)).strip()
        if weekly not in {str(v) for v, _l in WEEKDAYS}:
            errors["weekly_holiday"] = ["Choose a day of the week."]
        if not errors:
            if values["open_time"] == values["close_time"]:
                errors["close_time"] = ["The close time must differ from the open time."]
            if values["work_end"] <= values["work_start"]:
                errors["work_end"] = ["The working hours must end after they start."]
        if errors:
            raise ValidationError(errors)
        for name, value in values.items():
            setattr(s, name, value)
        s.weekly_holiday = int(weekly)
        s.save()
        audit.record(request, "Changed attendance settings",
                     f"open {s.open_time:%H:%M}, close {s.close_time:%H:%M}, working hours {s.work_start:%H:%M}–{s.work_end:%H:%M}, "
                     f"weekly holiday {dict(WEEKDAYS)[s.weekly_holiday]}")
        return Response(settings_payload(s))


# --- Office holidays ----------------------------------------------------------------------------

def holiday_row(h):
    return {"id": h.id, "name": h.name, "date": h.date, "description": h.description or None,
            "weekday": dict(WEEKDAYS)[h.date.weekday()], "updated_at": iso(h.updated_at)}


def read_holiday(d, current=None):
    errors = {}
    name = parsing.text(d, "name", 120, required=True, errors=errors, label="holiday name")
    day = parsing.date(d, "date", errors)
    if day and OfficeHoliday.objects.filter(date=day).exclude(pk=current.pk if current else None).exists():
        errors["date"] = [f"{day:%d %b %Y} is already an office holiday."]
    if errors:
        raise ValidationError(errors)
    return {"name": name, "date": day, "description": parsing.text(d, "description", 2000)}


def save_holiday(h):
    try:
        with transaction.atomic():
            h.save()
    except IntegrityError:  # two people saving the same date at once
        raise ValidationError({"date": ["This date is already an office holiday."]})


class HolidaysView(AttendanceView):
    """Office holidays, shown to everyone. ?year=YYYY or ?date_from=&date_to=. Adding needs holiday_manage."""

    def get(self, request):
        qs = OfficeHoliday.objects.all()
        year = self.int_param("year")
        if year:
            qs = qs.filter(date__year=year)
        start, end = optional_date(self.param("date_from"), "date_from"), optional_date(self.param("date_to"), "date_to")
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        return self.paginated(qs, holiday_row)

    def post(self, request):
        perms.require(request.user, "holiday_manage", "You don't have permission to add office holidays.")
        h = OfficeHoliday(created_by=request.user, **read_holiday(request.data))
        save_holiday(h)
        audit.record(request, "Added office holiday", f"{h.name} {h.date:%d %b %Y}")
        return Response(holiday_row(h), status=status.HTTP_201_CREATED)


class HolidayDetailView(AttendanceView):
    def patch(self, request, pk):
        perms.require(request.user, "holiday_manage", "You don't have permission to edit office holidays.")
        h = get_object_or_404(OfficeHoliday, pk=pk)
        current = {"name": h.name, "date": h.date.isoformat(), "description": h.description}
        for k, v in read_holiday({**current, **{k: request.data.get(k) for k in current if k in request.data}}, current=h).items():
            setattr(h, k, v)
        save_holiday(h)
        audit.record(request, "Edited office holiday", f"{h.name} {h.date:%d %b %Y}")
        return Response(holiday_row(h))

    def delete(self, request, pk):
        perms.require(request.user, "holiday_manage", "You don't have permission to delete office holidays.")
        h = get_object_or_404(OfficeHoliday, pk=pk)
        audit.record(request, "Deleted office holiday", f"{h.name} {h.date:%d %b %Y}")
        h.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Dashboard ----------------------------------------------------------------------------------

def on_permission_at(leaves, at):
    """Whether an approved permission covers this moment."""
    return any(lr.type == LeaveRequest.Type.PERMISSION and lr.from_time and lr.to_time
               and datetime.combine(lr.date, lr.from_time, tzinfo=window.IST) <= at < datetime.combine(lr.date, lr.to_time, tzinfo=window.IST)
               for lr in leaves)


class DashboardView(AttendanceView):
    """
    Everyone's attendance on one day (needs view_all): summary counts over the active employees matching
    ?employee=&department=&search=, and a table of them narrowed by ?status=, with ?page=. ?date= defaults to today.
    """

    def get(self, request):
        perms.require(request.user, "view_all", "You don't have permission to view everyone's attendance.")
        day = optional_date(self.param("date"), "date") or window.now().date()
        st = self.param("status") or None
        if st and st not in DAY_LABELS:
            raise ValidationError({"status": ["Unknown status."]})
        employees = current_employees().filter(status=Employee.Status.ACTIVE)
        emp_id = self.int_param("employee")
        if emp_id:
            employees = employees.filter(pk=emp_id)
        if self.param("department"):
            employees = employees.filter(department__iexact=self.param("department"))
        q = self.param("search")
        if q:
            employees = employees.filter(Q(name__icontains=q) | Q(employee_code__icontains=q) | Q(department__icontains=q))
        employees = list(employees.order_by("employee_code", "id"))
        pic, w, sched = services.picture(employees, day, day)
        is_today = day == w.at.date()
        summary = {"total_active": len(employees), "present": 0, "absent": 0, "on_leave": 0, "on_permission": 0,
                   "not_checked_out": 0}
        rows = []
        for emp in employees:
            entry = pic[emp.id].get(day)
            if entry is None:  # a day still to come, or before the employee joined
                holiday = sched.holiday(day)
                entry = {"statuses": [holiday] if holiday else [], "record": None, "leaves": [],
                         "figures": figures(None, [], sched, day)}
            rec, statuses, leaves = entry["record"], entry["statuses"], entry["leaves"]
            summary["present"] += rec is not None
            summary["absent"] += ABSENT in statuses
            summary["on_leave"] += LEAVE in statuses
            summary["not_checked_out"] += bool(rec and rec.check_out_at is None)
            summary["on_permission"] += (on_permission_at(leaves, w.at) if is_today
                                         else any(lr.type == LeaveRequest.Type.PERMISSION for lr in leaves))
            if st and st not in statuses:
                continue
            rows.append({"employee": employee_brief(emp), "date": day, "record_id": rec.id if rec else None,
                         "check_in_at": iso(rec.check_in_at) if rec else None, "check_out_at": iso(rec.check_out_at) if rec else None,
                         **figures_block(entry["figures"]), "permission_times": permission_times(leaves),
                         "statuses": statuses, "labels": [DAY_LABELS[s] for s in statuses],
                         "record_status": record_status(rec, w) if rec else None})
        response = self.get_paginated_response(self.paginate_queryset(rows))
        response.data.update(summary=summary, date=day, holiday=holiday_block(sched, day),
                             permission_label="Currently On Approved Permission" if is_today else "On Approved Permission")
        return response
