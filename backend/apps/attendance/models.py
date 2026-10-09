from datetime import time

from django.conf import settings
from django.db import models

from apps.system.models import SingletonModel

# Per-user permissions (Settings → Users), checked on the server for every Attendance action.
# A Super Admin has all of them. Stored with Django's built-in permission tables as "attendance.<code>".
PERMISSIONS = [
    ("check_in", "Check in"),
    ("check_out", "Check out / logout"),
    ("view_all", "View everyone's attendance (dashboard)"),
    ("leave_apply", "Apply for leave / permission"),
    ("leave_view", "View every employee's leave / permission requests"),
    ("leave_approve", "Approve leave / permission"),
    ("leave_reject", "Reject leave / permission"),
    ("employee_view", "View employees"),
    ("employee_manage", "Add / edit / delete employees"),
    ("calendar_view", "View every employee's calendar"),
    ("report_view", "View attendance reports"),
    ("report_export", "Export attendance reports (PDF / Excel / CSV)"),
    ("settings_view", "View attendance settings"),
    ("settings_manage", "Change attendance settings"),
    ("holiday_manage", "Add / edit / delete office holidays"),
]

WEEKDAYS = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")]


class AttendanceSettings(SingletonModel):
    """
    The daily attendance window: check-in is open from open_time to close_time the next morning and frozen in
    between. work_start / work_end are the office working hours (scheduled hours; permission is deducted only inside
    them). weekly_holiday is the weekly day off (Sunday by default).
    """

    open_time = models.TimeField(default=time(17, 0))
    close_time = models.TimeField(default=time(9, 20))
    work_start = models.TimeField(default=time(9, 0))
    work_end = models.TimeField(default=time(17, 30))
    weekly_holiday = models.PositiveSmallIntegerField(choices=WEEKDAYS, default=6)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        verbose_name_plural = "attendance settings"

    def __str__(self):
        return f"{self.open_time:%H:%M} → {self.close_time:%H:%M}"


class Employee(models.Model):
    """A person whose attendance is kept. Linked to a portal login when they mark their own attendance."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    employee_code = models.CharField("employee ID", max_length=30)
    name = models.CharField(max_length=150)
    department = models.CharField(max_length=100, blank=True, db_index=True)
    designation = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    joining_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="employee")
    # Deleting removes the employee from the list but keeps their attendance and leave history
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=["employee_code"], condition=models.Q(deleted_at__isnull=True),
                                               name="unique_current_employee_code")]

    def __str__(self):
        return f"{self.employee_code} {self.name}"


class AttendanceRecord(models.Model):
    """One employee's check-in (and check-out) for one attendance window, with real server times."""

    class Status(models.TextChoices):
        CHECKED_IN = "checked_in", "Checked in"
        COMPLETED = "completed", "Attendance completed"

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="attendance")
    # The date the window opened: a check-in at 2 AM belongs to the previous evening's window
    attendance_date = models.DateField(db_index=True)
    check_in_at = models.DateTimeField()
    check_out_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CHECKED_IN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-attendance_date", "-id"]
        default_permissions = ()
        permissions = PERMISSIONS
        constraints = [models.UniqueConstraint(fields=["employee", "attendance_date"], name="one_attendance_per_window")]

    def __str__(self):
        return f"{self.employee} {self.attendance_date}"

    @property
    def duration(self):
        return self.check_out_at - self.check_in_at if self.check_out_at else None


class LeaveRequest(models.Model):
    class Type(models.TextChoices):
        LEAVE = "leave", "Leave"
        PERMISSION = "permission", "Permission"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="leave_requests")
    type = models.CharField(max_length=10, choices=Type.choices)
    date = models.DateField(db_index=True)
    from_time = models.TimeField(null=True, blank=True)  # optional for a whole-day leave
    to_time = models.TimeField(null=True, blank=True)
    reason = models.CharField(max_length=255)
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        default_permissions = ()

    def __str__(self):
        return f"{self.get_type_display()} {self.employee} {self.date}"


class OfficeHoliday(models.Model):
    """A company holiday: nobody is absent that day and it isn't a scheduled working day."""

    name = models.CharField(max_length=120)
    date = models.DateField(unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date"]
        default_permissions = ()

    def __str__(self):
        return f"{self.date} {self.name}"
