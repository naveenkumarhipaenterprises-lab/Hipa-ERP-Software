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
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core import parsing
from apps.core.roles import ATTENDANCE_MANAGERS, has_any_role
from apps.core.views import ModuleAPIView
from services import audit
from services.exporters import MIME, export

from . import permissions as perms
from . import location, reports, services, window
from .models import WEEKDAYS, AttendanceRecord, AttendanceSettings, Employee, EmployeeFile, LeaveRequest, OfficeHoliday
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


def employee_row(e, contacts=True):
    """contacts=False (people who may only view employees): no e-mail or phone number."""
    return {**employee_brief(e), "designation": e.designation or None,
            "email": (e.email or None) if contacts else None, "phone": (e.phone or None) if contacts else None,
            "joining_date": e.joining_date, "status": e.get_status_display(), "status_value": e.status,
            "user": {"id": e.user_id, "name": e.user.name or e.user.username, "email": e.user.email if contacts else None}
            if e.user_id else None}


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
            "check_in_location": location.block(r, "check_in"), "check_out_location": location.block(r, "check_out"),
            "entered_by": (r.entered_by.name or r.entered_by.username) if r.entered_by_id else None, "note": r.note or None,
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
    # During the overnight check-in window, an evening check-in belongs to the
    # following work day. Use that same date for both the duplicate check and
    # the record shown in the Today's Attendance card.
    work_date = w.checkin_date if w.is_open else today
    flags = perms.flags(user)
    to_close = services.open_record(emp, w) if emp else None
    taken = bool(emp and w.is_open and AttendanceRecord.objects.filter(employee=emp, attendance_date=w.checkin_date).exists())
    can_in = bool(w.is_open and emp and not taken)  # no permission needed: own attendance only
    can_out = bool(to_close)
    # The work day to show: the open record, otherwise the active work date.
    record = to_close or (AttendanceRecord.objects.filter(employee=emp, attendance_date=work_date).first() if emp else None)
    if not record and emp and work_date != today:
        record = AttendanceRecord.objects.filter(employee=emp, attendance_date=today).first()
    work_date = record.attendance_date if record else work_date
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
        "location_required": s.require_location,
        "permissions": flags,
    }


class StatusView(AttendanceView):
    def get(self, request):
        return Response(status_payload(request.user))


class CheckInView(AttendanceView):
    def post(self, request):
        # The time is the server's; only the device's GPS location is taken from the request
        try:
            services.check_in(request.user, request.data)
        except ValidationError as exc:
            # A double-click, retry, or second browser tab can reach the API
            # after the first request has already created the record. Return
            # the authoritative state instead of leaving the UI stale with a
            # misleading "Not checked in" card.
            detail = exc.detail.get("detail") if isinstance(exc.detail, dict) else None
            if isinstance(detail, (list, tuple)):
                detail = detail[0] if detail else None
            if isinstance(detail, str) and detail.startswith("You have already checked in"):
                return Response(status_payload(request.user))
            raise
        return Response(status_payload(request.user), status=status.HTTP_201_CREATED)


class CheckOutView(AttendanceView):
    def post(self, request):
        services.check_out(request.user, request.data)
        return Response(status_payload(request.user))


class HistoryView(AttendanceView):
    """The signed-in employee's own attendance, newest first."""

    def get(self, request):
        emp = employee_of(request.user)
        qs = AttendanceRecord.objects.select_related("employee").filter(employee=emp) if emp else AttendanceRecord.objects.none()
        return self.get_paginated_response(record_rows(self.paginate_queryset(qs), window.state()))


def is_attendance_manager(user):
    return has_any_role(user, ATTENDANCE_MANAGERS)


def require_attendance_manager(user):
    if not is_attendance_manager(user):
        raise PermissionDenied("Only a Super Admin or Management can enter attendance for someone else.")


def read_clock(d, name, errors, label, required=True):
    raw = str(d.get(name) or "").strip()
    if not raw:
        if required:
            errors[name] = [f"Enter the {label} time."]
        return None
    try:
        return datetime.strptime(raw, "%H:%M").time()
    except ValueError:
        errors[name] = [f"Enter the {label} time as HH:MM (24-hour)."]
        return None


class RecordsView(AttendanceView):
    """Everyone's attendance records (reports permission, or Super Admin / Management).
    POST: a Super Admin or Management enters or corrects one employee's attendance for a work day (forgot to check in
    or out, came late). An existing record for that day is corrected; every entry is marked with who made it."""

    def get(self, request):
        if not is_attendance_manager(request.user):
            perms.require(request.user, "report_view", "You don't have permission to view everyone's attendance.")
        qs = AttendanceRecord.objects.select_related("employee", "entered_by")
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
        if self.param("search"):
            q = self.param("search")
            qs = qs.filter(Q(employee__name__icontains=q) | Q(employee__employee_code__icontains=q))
        return self.get_paginated_response(record_rows(self.paginate_queryset(qs), window.state()))

    def post(self, request):
        """record_id (optional): the record being corrected, which then moves if its employee or work date changes."""
        require_attendance_manager(request.user)
        d, errors = request.data, {}
        emp = parsing.record(d, "employee_id", current_employees(), errors, message="Choose an employee.")
        current = None
        if d.get("record_id") not in (None, ""):
            current = parsing.record(d, "record_id", AttendanceRecord.objects.all(), errors, message="This record no longer exists.")
        day = parsing.date(d, "date", errors, label="work date")
        t_in = read_clock(d, "check_in", errors, "check-in")
        t_out = read_clock(d, "check_out", errors, "check-out", required=False)
        note = parsing.text(d, "note", 200, required=True, errors=errors, label="reason")
        now = window.now()
        if day and day > now.date():
            errors["date"] = ["The work date can't be in the future."]
        if errors:
            raise ValidationError(errors)
        # The same work-day rule as a self check-in: from the Check-In opening time (overnight window) it is the
        # evening before the work date, e.g. 6:00 PM for 15 Oct is 14 Oct 6:00 PM.
        s = AttendanceSettings.load()
        evening = s.close_time <= s.open_time and t_in >= s.open_time
        check_in_at = datetime.combine(day - window.DAY if evening else day, t_in, tzinfo=window.IST)
        check_out_at = None
        if t_out:
            check_out_at = datetime.combine(day, t_out, tzinfo=window.IST)
            if check_out_at <= check_in_at:  # e.g. a night shift: check-out the next morning
                check_out_at += window.DAY
        if check_in_at > now or (check_out_at and check_out_at > now):
            raise ValidationError({"detail": "Times can't be in the future."})
        try:
            with transaction.atomic():
                record = AttendanceRecord.objects.select_for_update().filter(employee=emp, attendance_date=day).first()
                if current is not None and record is not None and record.pk != current.pk:
                    raise ValidationError({"date": [f"{emp.name} already has a record for {day:%d %b %Y}. Correct that one instead."]})
                if current is not None and record is None:  # the corrected record moves to the new employee / date
                    record = AttendanceRecord.objects.select_for_update().get(pk=current.pk)
                created = record is None
                record = record or AttendanceRecord(employee=emp, attendance_date=day)
                before = None if created else (record.check_in_at, record.check_out_at)
                record.employee, record.attendance_date = emp, day
                record.check_in_at, record.check_out_at = check_in_at, check_out_at
                record.status = AttendanceRecord.Status.COMPLETED if check_out_at else AttendanceRecord.Status.CHECKED_IN
                record.entered_by, record.note = request.user, note
                record.save()
        except IntegrityError:  # someone saved the same employee and day at the same moment
            raise ValidationError({"detail": "This attendance was just saved by someone else. Reload and try again."})
        times = f"{window.clock(check_in_at)}" + (f" – {window.clock(check_out_at)}" if check_out_at else "")
        audit.record(request, f"{'Entered' if created else 'Corrected'} attendance {day:%d %b %Y} ({times})"[:200],
                     f"{emp.employee_code} {emp.name}" + ("" if created else f" (was {window.clock(before[0])}"
                     + (f" – {window.clock(before[1])})" if before[1] else ")")))
        record = AttendanceRecord.objects.select_related("employee", "entered_by").get(pk=record.pk)
        return Response(record_rows([record], window.state())[0], status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class RecordDetailView(AttendanceView):
    """A Super Admin deletes a wrong attendance record (the route-level rule: deleting is for Super Admins)."""

    def delete(self, request, pk):
        record = get_object_or_404(AttendanceRecord.objects.select_related("employee"), pk=pk)
        label = f"{record.employee.employee_code} {record.employee.name}"
        day = record.attendance_date
        record.delete()
        audit.record(request, f"Deleted attendance record {day:%d %b %Y}", label)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        data["can_enter_attendance"] = is_attendance_manager(user)
        data["can_delete"] = has_any_role(user, ["admin"])
        if data["can_enter_attendance"] or any(flags[c] for c in ("view_all", "employee_view", "employee_manage", "leave_view",
                                                                    "calendar_view", "report_view")):
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
        contacts = perms.has(request.user, "employee_manage")
        q = self.param("search")
        if q:
            match = Q(name__icontains=q) | Q(employee_code__icontains=q) | Q(department__icontains=q)
            qs = qs.filter(match | Q(email__icontains=q) if contacts else match)
        st = self.param("status")
        if st:
            if st not in Employee.Status.values:
                raise ValidationError({"status": ["Use active or inactive."]})
            qs = qs.filter(status=st)
        if self.param("department"):
            qs = qs.filter(department__iexact=self.param("department"))
        return self.paginated(qs, lambda e: employee_row(e, contacts))

    def post(self, request):
        perms.require(request.user, "employee_manage", "You don't have permission to manage employees.")
        e = Employee.objects.create(**read_employee(request.data))
        audit.record(request, "Added employee", f"{e.employee_code} {e.name}")
        return Response(employee_row(e), status=status.HTTP_201_CREATED)


class EmployeeDetailView(AttendanceView):
    def get(self, request, pk):
        perms.require_any(request.user, ("employee_view", "employee_manage"), "You don't have permission to view employees.")
        return Response(employee_row(get_object_or_404(employees_qs(), pk=pk), perms.has(request.user, "employee_manage")))

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


# --- Employee photo and documents -----------------------------------------------------------------

MAX_FILE_MB = 5
MAX_DOCUMENTS = 20
# What may be uploaded, by file extension; the stored content type comes from here, never from the client
FILE_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp",
              "pdf": "application/pdf", "doc": "application/msword",
              "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              "xls": "application/vnd.ms-excel",
              "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
PHOTO_TYPES = {"jpg", "jpeg", "png", "webp"}


def file_row(f):
    return {"id": f.id, "kind": f.kind, "name": f.name, "content_type": f.content_type, "size": f.size,
            "uploaded_by": f.uploaded_by.name or f.uploaded_by.username if f.uploaded_by_id else None,
            "uploaded_at": iso(f.created_at)}


def employee_for_files(request, pk, manage):
    """The employee whose files are asked for. Managers (employee_view / employee_manage) reach everyone;
    every employee reaches their own photo and documents."""
    e = get_object_or_404(employees_qs(), pk=pk)
    if e.user_id == request.user.id:
        return e
    codes = ("employee_manage",) if manage else ("employee_view", "employee_manage")
    perms.require_any(request.user, codes, "You don't have permission to " + ("manage" if manage else "view") + " employee files.")
    return e


class EmployeeFilesView(AttendanceView):
    def get(self, request, pk):
        e = employee_for_files(request, pk, manage=False)
        return Response({"results": [file_row(f) for f in e.files.defer("data")]})

    def post(self, request, pk):
        e = employee_for_files(request, pk, manage=True)
        upload = request.FILES.get("file")
        if not upload:
            raise ValidationError({"file": ["Choose a file to upload."]})
        kind = request.data.get("kind", EmployeeFile.Kind.DOCUMENT)
        if kind not in EmployeeFile.Kind.values:
            raise ValidationError({"kind": ["Use photo or document."]})
        ext = upload.name.rsplit(".", 1)[-1].lower() if "." in upload.name else ""
        allowed = PHOTO_TYPES if kind == EmployeeFile.Kind.PHOTO else FILE_TYPES
        if ext not in allowed:
            raise ValidationError({"file": [("A photo must be a JPG, PNG or WEBP image." if kind == EmployeeFile.Kind.PHOTO
                                             else "Allowed files: JPG, PNG, WEBP, PDF, Word (DOC/DOCX), Excel (XLS/XLSX).")]})
        if upload.size > MAX_FILE_MB * 1024 * 1024:
            raise ValidationError({"file": [f"The file is too big. The limit is {MAX_FILE_MB} MB."]})
        if kind == EmployeeFile.Kind.DOCUMENT and e.files.filter(kind=kind).count() >= MAX_DOCUMENTS:
            raise ValidationError({"file": [f"At most {MAX_DOCUMENTS} documents per employee. Delete one first."]})
        name = re.sub(r"[\r\n\t\"\\]", "", upload.name).strip()[:150] or f"file.{ext}"
        with transaction.atomic():
            if kind == EmployeeFile.Kind.PHOTO:  # one photo per employee: a new one replaces it
                e.files.filter(kind=EmployeeFile.Kind.PHOTO).delete()
            f = EmployeeFile.objects.create(employee=e, kind=kind, name=name, content_type=FILE_TYPES[ext],
                                            size=upload.size, data=upload.read(), uploaded_by=request.user)
        audit.record(request, "Uploaded employee " + ("photo" if kind == EmployeeFile.Kind.PHOTO else "document"),
                     f"{e.employee_code} {e.name}: {name}")
        return Response(file_row(f), status=status.HTTP_201_CREATED)


class EmployeeFileDetailView(AttendanceView):
    def get(self, request, pk, fid):
        e = employee_for_files(request, pk, manage=False)
        f = get_object_or_404(e.files, pk=fid)
        response = HttpResponse(bytes(f.data), content_type=f.content_type)
        disposition = "inline" if f.content_type.startswith("image/") or f.content_type == "application/pdf" else "attachment"
        response["Content-Disposition"] = f'{disposition}; filename="{f.name}"'
        return response

    def delete(self, request, pk, fid):
        e = employee_for_files(request, pk, manage=True)
        f = get_object_or_404(e.files, pk=fid)
        audit.record(request, "Deleted employee file", f"{e.employee_code} {e.name}: {f.name}")
        f.delete()
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


def check_leave_day(emp, data, exclude=None):
    """A request can't fall on a holiday or clash with the employee's other pending / approved requests that day:
    a whole-day request clashes with anything, timed requests only when their times overlap."""
    day, start, end = data["date"], data["from_time"], data["to_time"]
    sched = schedule_for([day])
    if sched.holiday(day):
        raise ValidationError({"date": [f"{day:%d %b %Y} is a holiday ({holiday_block(sched, day)['name']}): "
                                        "no leave or permission is needed."]})
    others = LeaveRequest.objects.filter(employee=emp, date=day, status__in=(LS.PENDING, LS.APPROVED))
    if exclude is not None:
        others = others.exclude(pk=exclude.pk)
    for other in others:
        timed = start and end and other.from_time and other.to_time
        if not timed or (start < other.to_time and other.from_time < end):
            when = f"{other.from_time:%H:%M}–{other.to_time:%H:%M}" if other.from_time and other.to_time else "whole day"
            raise ValidationError({"date": [f"There is already a {other.get_status_display().lower()} "
                                            f"{other.get_type_display().lower()} request for this day ({when})."]})


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
        data = read_leave(request.data)
        with transaction.atomic():
            Employee.objects.select_for_update().get(pk=emp.pk)  # two requests sent at once can't both pass the check
            check_leave_day(emp, data)
            lr = LeaveRequest.objects.create(employee=emp, requested_by=request.user, **data)
        audit.record(request, f"Requested {lr.get_type_display().lower()}", f"{emp.name} {lr.date:%d %b %Y}")
        return Response(leave_row(lr, request.user), status=status.HTTP_201_CREATED)


class LeaveDetailView(AttendanceView):
    def patch(self, request, pk):
        perms.require(request.user, "leave_apply", "You don't have permission to apply for leave or permission.")
        with transaction.atomic():
            lr = get_object_or_404(leave_qs().select_for_update(of=("self",)), pk=pk)
            if not (lr.requested_by_id == request.user.id or lr.employee.user_id == request.user.id):
                raise PermissionDenied("You can only change your own requests.")
            if lr.status != LS.PENDING:
                raise ValidationError({"detail": f"A {lr.get_status_display().lower()} request can't be changed."})
            current = {"type": lr.type, "date": lr.date.isoformat(), "from_time": lr.from_time.strftime("%H:%M") if lr.from_time else "",
                       "to_time": lr.to_time.strftime("%H:%M") if lr.to_time else "", "reason": lr.reason, "remarks": lr.remarks}
            data = read_leave({**current, **{k: request.data.get(k) for k in current if k in request.data}})
            Employee.objects.select_for_update().get(pk=lr.employee_id)
            check_leave_day(lr.employee, data, exclude=lr)
            for k, v in data.items():
                setattr(lr, k, v)
            lr.save()
        return Response(leave_row(lr, request.user))


class LeaveActionView(AttendanceView):
    """POST approve | reject (by permission) or cancel (own pending request)."""

    ACTIONS = {"approve": (LS.APPROVED, "leave_approve"), "reject": (LS.REJECTED, "leave_reject"), "cancel": (LS.CANCELLED, None)}

    def post(self, request, pk, action):
        if action not in self.ACTIONS:
            raise NotFound("Unknown action. Use approve, reject or cancel.")
        new, code = self.ACTIONS[action]
        with transaction.atomic():
            lr = get_object_or_404(leave_qs().select_for_update(of=("self",)), pk=pk)
            own = lr.requested_by_id == request.user.id or lr.employee.user_id == request.user.id
            if code:
                perms.require(request.user, code, f"You don't have permission to {action} requests.")
                if own and role_of(request.user) != Role.ADMIN:
                    raise PermissionDenied(f"You can't {action} your own request. Ask another approver.")
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
            "require_location": s.require_location,
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
        require_location = s.require_location
        if "require_location" in request.data:
            raw = request.data.get("require_location")
            require_location = raw if isinstance(raw, bool) else str(raw).strip().lower() in ("true", "1", "yes", "on")
        if errors:
            raise ValidationError(errors)
        for name, value in values.items():
            setattr(s, name, value)
        s.weekly_holiday = int(weekly)
        s.require_location = require_location
        s.save()
        audit.record(request, "Changed attendance settings",
                     f"open {s.open_time:%H:%M}, close {s.close_time:%H:%M}, working hours {s.work_start:%H:%M}–{s.work_end:%H:%M}, "
                     f"weekly holiday {dict(WEEKDAYS)[s.weekly_holiday]}, location {'required' if s.require_location else 'optional'}")
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
                         "check_in_location": location.block(rec, "check_in"),
                         "check_out_location": location.block(rec, "check_out"),
                         "entered_by": (rec.entered_by.name or rec.entered_by.username) if rec and rec.entered_by_id else None,
                         **figures_block(entry["figures"]), "permission_times": permission_times(leaves),
                         "statuses": statuses, "labels": [DAY_LABELS[s] for s in statuses],
                         "record_status": record_status(rec, w) if rec else None})
        response = self.get_paginated_response(self.paginate_queryset(rows))
        response.data.update(summary=summary, date=day, holiday=holiday_block(sched, day),
                             permission_label="Currently On Approved Permission" if is_today else "On Approved Permission")
        return response
