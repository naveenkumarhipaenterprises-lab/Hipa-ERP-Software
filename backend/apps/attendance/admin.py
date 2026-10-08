from django.contrib import admin

from .models import AttendanceRecord, Employee, LeaveRequest


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "name", "department", "designation", "status", "user", "deleted_at")
    list_filter = ("status", "department")
    search_fields = ("employee_code", "name", "email")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    """Read-only: times come only from the server's check-in / check-out."""

    list_display = ("attendance_date", "employee", "check_in_at", "check_out_at", "status")
    list_filter = ("status", "attendance_date")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("date", "employee", "type", "from_time", "to_time", "status", "reviewed_by")
    list_filter = ("type", "status")
