import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import LoginActivity
from apps.core.exceptions import NotConfigured
from apps.core.metrics import choices
from apps.attendance import permissions as attendance_perms
from apps.core.roles import Role
from apps.core.views import ModuleAPIView, ModuleMixin
from services import audit, notifications
from services.backup import run_backup

from . import serializers as s
from .models import AuditLog, BackupRun, BackupSettings, BillingSettings, CompanySettings, Notification, NotificationPreference

User = get_user_model()


def pairs(items):
    return [{"value": v, "label": l} for v, l in items]


class SettingsView(ModuleAPIView):
    module = "settings"


class OptionsView(SettingsView):
    def get(self, request):
        return Response({
            "timezones": [{"value": tz, "label": tz.replace("_", " ")} for tz in s.timezones()],
            "date_formats": pairs(s.DATE_FORMATS),
            "time_formats": pairs(s.TIME_FORMATS),
            "currencies": pairs(s.CURRENCIES),
            "languages": pairs(s.LANGUAGES),
            "roles": choices(Role),
            "attendance_permissions": [{"value": code, "label": label} for code, label in attendance_perms.LABELS.items()],
            "user_statuses": pairs(s.USER_STATUSES),
            "backup_retention": pairs(BackupSettings.RETENTION_CHOICES),
        })


class _SingletonFormView(SettingsView):
    serializer_class = None
    model = CompanySettings
    label = ""

    def get(self, request):
        return Response(self.serializer_class(self.model.load()).data)

    def put(self, request):
        ser = self.serializer_class(self.model.load(), data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        audit.record(request, f"Updated {self.label}")
        return Response(ser.data)


class GeneralSettingsView(_SingletonFormView):
    serializer_class = s.GeneralSettingsSerializer
    label = "general settings"


class CompanySettingsView(_SingletonFormView):
    serializer_class = s.CompanyDetailsSerializer
    label = "company details"


class BillingSettingsView(_SingletonFormView):
    serializer_class = s.BillingSettingsSerializer
    model = BillingSettings
    label = "tax & billing settings"


def send_invitation(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    send_mail(
        "You're invited to the HIPA MASALA portal",
        f"Hello {user.name},\n\nAn account has been created for you (username: {user.username}).\n"
        f"Set your password here to get started:\n{link}\n",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )


def unique_username(email):
    base = re.sub(r"[^\w.@+-]", "", email.split("@")[0])[:140] or "user"
    candidate, n = base, 1
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f"{base}{n}"
    return candidate


class UsersView(ModuleMixin, generics.GenericAPIView):
    module = "settings"
    serializer_class = s.UserRowSerializer

    def get(self, request):
        qs = User.objects.prefetch_related("user_permissions__content_type").order_by("name", "id")
        q = request.query_params.get("search", "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(username__icontains=q))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def post(self, request):
        data = s.InviteUserSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        if v["role"] == Role.ADMIN and request.user.effective_role != Role.ADMIN:
            raise PermissionDenied("Only a Super Admin can invite another Super Admin.")
        with transaction.atomic():
            user = User(username=unique_username(v["email"]), email=v["email"], name=v["name"].strip(), role=v["role"])
            user.set_unusable_password()
            user.save()
            try:
                send_invitation(user)
            except Exception as exc:
                raise NotConfigured("The invitation e-mail could not be sent. Check the e-mail settings in .env.") from exc
        audit.record(request, "Invited user", f"{user.name} <{user.email}>")
        return Response(s.UserRowSerializer(user).data, status=status.HTTP_201_CREATED)


class UserDetailView(SettingsView):
    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        data = s.UpdateUserSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        me = request.user
        is_admin = me.effective_role == Role.ADMIN
        if user.pk == me.pk and (("role" in v and v["role"] != me.effective_role) or v.get("status") == "inactive"):
            raise ValidationError({"detail": "You can't change your own role or deactivate yourself."})
        if not is_admin and (user.effective_role == Role.ADMIN or v.get("role") == Role.ADMIN):
            raise PermissionDenied("Only a Super Admin can change Super Admin accounts.")
        if user.is_superuser and "role" in v and v["role"] != Role.ADMIN:
            raise ValidationError({"role": ["This account is a Django superuser; change it in the admin site."]})

        changes = []
        if "name" in v and v["name"].strip() != user.name:
            user.name = v["name"].strip()
            changes.append("name")
        if "role" in v and v["role"] != user.role and not user.is_superuser:
            user.role = v["role"]
            changes.append(f"role → {Role(v['role']).label}")
        if "status" in v and (v["status"] == "active") != user.is_active:
            user.is_active = v["status"] == "active"
            changes.append("activated" if user.is_active else "deactivated")
        if "attendance_permissions" in v and user.effective_role != Role.ADMIN:  # a Super Admin always has all
            wanted = sorted(set(v["attendance_permissions"]))
            if wanted != attendance_perms.granted(user):
                attendance_perms.set_granted(user, wanted)
                changes.append("attendance permissions: " + (", ".join(attendance_perms.LABELS[c] for c in wanted) or "none"))
        user.save()
        if changes:
            audit.record(request, f"Updated user ({', '.join(changes)})"[:200], user.email)
        return Response(s.UserRowSerializer(user).data)


class NotificationPreferencesView(SettingsView):
    def get(self, request):
        return Response(notifications.preferences())

    def patch(self, request):
        key = request.data.get("key")
        enabled = request.data.get("enabled")
        if key not in notifications.CATALOGUE:
            raise ValidationError({"key": ["Unknown notification type."]})
        if not isinstance(enabled, bool):
            raise ValidationError({"enabled": ["Must be true or false."]})
        NotificationPreference.objects.update_or_create(key=key, defaults={"enabled": enabled})
        audit.record(request, f"{'Enabled' if enabled else 'Disabled'} notifications", notifications.CATALOGUE[key][0])
        return Response({"key": key, "enabled": enabled})


def backup_state():
    cfg = BackupSettings.load()
    last = BackupRun.objects.first()
    return {
        "automatic": cfg.automatic,
        "retention_months": cfg.retention_months,
        "last_backup_at": last.finished_at or last.started_at if last else None,
        "last_backup_status": last.get_status_display() if last else None,
    }


class BackupView(SettingsView):
    def get(self, request):
        return Response(backup_state())

    def patch(self, request):
        ser = s.BackupSettingsSerializer(BackupSettings.load(), data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        audit.record(request, "Updated backup settings")
        return Response(backup_state())


class RunBackupView(SettingsView):
    def post(self, request):
        run = run_backup(request.user)
        audit.record(request, "Ran manual backup", run.get_status_display())
        if run.status == BackupRun.Status.FAILED:
            return Response({"detail": f"Backup failed: {run.error}", "status": "Failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"status": "Completed", "file": run.file_name})


def integrations():
    email_on = bool(settings.EMAIL_HOST) and "smtp" in settings.EMAIL_BACKEND
    ai_on = bool(settings.GEMINI_API_KEY)
    return [
        {"key": "email", "name": "E-mail (SMTP)", "description": "Password resets, invitations and customer offers",
         "connected": email_on, "connected_at": None},
        {"key": "ai_engine", "name": "Google Gemini", "description": "Answers questions in the AI Assistant",
         "connected": ai_on, "connected_at": None},
    ]


class IntegrationsView(SettingsView):
    def get(self, request):
        return Response(integrations())


class IntegrationActionView(SettingsView):
    def post(self, request, key, action):
        if key not in {i["key"] for i in integrations()}:
            return Response({"detail": "Unknown integration."}, status=status.HTTP_404_NOT_FOUND)
        raise NotConfigured(
            "This integration is configured on the server: set its credentials in backend/.env and restart the backend."
        )


class SecurityView(SettingsView):
    def get(self, request):
        return Response({"two_factor_enabled": False})

    def patch(self, request):
        if request.data.get("two_factor_enabled"):
            raise ValidationError({"two_factor_enabled": ["Two-factor authentication is not available yet."]})
        return Response({"two_factor_enabled": False})


def device_of(agent):
    if not agent:
        return None
    browser = next((b for b in ("Edg", "OPR", "Chrome", "Firefox", "Safari") if b in agent), None)
    system = next((o for o in ("Windows", "Android", "iPhone", "iPad", "Mac OS", "Linux") if o in agent), None)
    browser = {"Edg": "Edge", "OPR": "Opera"}.get(browser, browser)
    return " on ".join(x for x in (browser, system) if x) or agent[:60]


class LoginActivityView(ModuleMixin, generics.GenericAPIView):
    module = "settings"

    def get(self, request):
        page = self.paginate_queryset(LoginActivity.objects.select_related("user"))
        rows = [
            {"id": a.id, "user": (a.user.name or a.user.username) if a.user else a.username_attempted,
             "device": device_of(a.user_agent), "ip": a.ip, "location": None, "time": a.created_at, "success": a.success}
            for a in page
        ]
        return self.get_paginated_response(rows)


class AuditLogsView(ModuleMixin, generics.GenericAPIView):
    module = "settings"
    serializer_class = s.AuditLogSerializer

    def get(self, request):
        qs = AuditLog.objects.select_related("user")
        q = request.query_params.get("search", "").strip()
        if q:
            qs = qs.filter(Q(action__icontains=q) | Q(target__icontains=q) | Q(user__name__icontains=q) | Q(user__email__icontains=q))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


# --- Notifications (every signed-in user, their own only) ------------------------
class NotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)
        return Response({
            "count": qs.count(),
            "next": None,
            "previous": None,
            "results": s.NotificationSerializer(qs[:50], many=True).data,  # the bell shows the latest 50
            "unread_count": qs.filter(read=False).count(),
        })


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        n = get_object_or_404(Notification, pk=pk, user=request.user)
        if not n.read:
            n.read = True
            n.save(update_fields=["read"])
        return Response(s.NotificationSerializer(n).data)


class NotificationsReadAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response({"updated": updated})
