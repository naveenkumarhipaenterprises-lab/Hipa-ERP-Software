"""
Attendance API. Every signed-in user can open the module; each action checks its own per-user permission
(permissions.py) on the server, and check-in / check-out also need the attendance window to be open (window.py).
"""
import re
from calendar import monthrange
from datetime import date, datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
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
from .models import AttendanceRecord, AttendanceSettings, Employee, LeaveRequest
from .services import DAY_LABELS, current_employees, duration_label, employee_of, record_status

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


def record_row(r, w):
    return {"id": r.id, "attendance_date": r.attendance_date, "employee": employee_brief(r.employee),
            "check_in_at": iso(r.check_in_at), "check_out_at": iso(r.check_out_at),
            "duration": duration_label(r.duration), "status": record_status(r, w)}


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
    return {"is_open": w.is_open, "attendance_date": w.attendance_date, "opens_at": iso(w.opens_at), "closes_at": iso(w.closes_at),
            "open_time": s.open_time.strftime("%H:%M"), "close_time": s.close_time.strftime("%H:%M"),
            "message": None if w.is_open else window.closed_message(w)}


# --- Attendance ------------------------------------------------------------------------------------

def status_payload(user):
    s = AttendanceSettings.load()
    w = window.state(settings=s)
    emp = employee_of(user)
    record = (AttendanceRecord.objects.select_related("employee").filter(employee=emp, attendance_date=w.last_date).first()
              if emp else None)
    current = record if (record and w.is_open) else None
    flags = perms.flags(user)
    return {
        "server_time": iso(window.now()),
        "timezone": "Asia/Kolkata (IST)",
        "window": window_block(w, s),
        "employee": employee_brief(emp) if emp else None,
        "record": record_row(record, w) if record else None,
        "can_check_in": bool(flags["check_in"] and w.is_open and emp and current is None),
        "can_check_out": bool(flags["check_out"] and w.is_open and current and current.check_out_at is None),
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
        w = window.state()
        return self.paginated(qs, lambda r: record_row(r, w))


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
        w = window.state()
        return self.paginated(qs, lambda r: record_row(r, w))


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
            "departments": sorted({d for d in current_employees().exclude(department="").values_list("department", flat=True)}),
            "employees": [],
            "users": [],
        }
        if any(flags[c] for c in ("employee_manage", "leave_view", "calendar_view", "report_view")):
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
        perms.require(request.user, "employee_manage", "You don't have permission to manage employees.")
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
        perms.require(request.user, "employee_manage", "You don't have permission to manage employees.")
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
            return Response({"month": raw, "employee": None, "days": []})
        pic, w = services.picture([emp], start, end)
        out = []
        for d, day in sorted(pic[emp.id].items()):
            rec = day["record"]
            out.append({"date": d, "statuses": day["statuses"], "labels": [DAY_LABELS[s] for s in day["statuses"]],
                        "check_in_at": iso(rec.check_in_at) if rec else None, "check_out_at": iso(rec.check_out_at) if rec else None,
                        "duration": duration_label(rec.duration) if rec else None,
                        "leaves": [{"type": lr.get_type_display(), "from_time": lr.from_time.strftime("%H:%M") if lr.from_time else None,
                                    "to_time": lr.to_time.strftime("%H:%M") if lr.to_time else None, "reason": lr.reason}
                                   for lr in day["leaves"]]})
        return Response({"month": raw, "employee": employee_brief(emp), "days": out})


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
        content, mime = export(data, fmt)
        response = HttpResponse(content, content_type=mime)
        response["Content-Disposition"] = f'attachment; filename="hipa-attendance-{kind}-{start:%Y%m%d}-{end:%Y%m%d}.{fmt}"'
        audit.record(request, "Exported attendance report", f"{kind} {start} – {end} {fmt}")
        return response


# --- Settings -----------------------------------------------------------------------------------

def settings_payload(s):
    return {"open_time": s.open_time.strftime("%H:%M"), "close_time": s.close_time.strftime("%H:%M"),
            "timezone": "Asia/Kolkata (IST)", "updated_at": iso(s.updated_at)}


class SettingsView(AttendanceView):
    def get(self, request):
        return Response(settings_payload(AttendanceSettings.load()))

    def patch(self, request):
        perms.require(request.user, "settings_manage", "You don't have permission to change attendance settings.")
        s = AttendanceSettings.load()
        errors = {}
        open_t = read_time(request.data, "open_time", errors) if "open_time" in request.data else s.open_time
        close_t = read_time(request.data, "close_time", errors) if "close_time" in request.data else s.close_time
        if not errors:
            if open_t is None:
                errors["open_time"] = ["Enter the open time."]
            if close_t is None:
                errors["close_time"] = ["Enter the close time."]
            if open_t and close_t and open_t == close_t:
                errors["close_time"] = ["The close time must differ from the open time."]
        if errors:
            raise ValidationError(errors)
        s.open_time, s.close_time = open_t, close_t
        s.save()
        audit.record(request, "Changed attendance window", f"{open_t:%H:%M} → {close_t:%H:%M}")
        return Response(settings_payload(s))
