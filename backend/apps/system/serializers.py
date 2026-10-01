from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.core.roles import Role

from .models import AuditLog, BackupSettings, CompanySettings, Notification

User = get_user_model()

DATE_FORMATS = [
    ("DD/MM/YYYY", "DD/MM/YYYY"),
    ("MM/DD/YYYY", "MM/DD/YYYY"),
    ("YYYY-MM-DD", "YYYY-MM-DD"),
    ("DD MMM YYYY", "DD MMM YYYY"),
]
TIME_FORMATS = [("12h", "12-hour"), ("24h", "24-hour")]
CURRENCIES = [("INR", "Indian Rupee (₹)"), ("USD", "US Dollar ($)"), ("EUR", "Euro (€)"), ("GBP", "British Pound (£)"), ("AED", "UAE Dirham")]
LANGUAGES = [("en", "English")]
USER_STATUSES = [("Active", "Active"), ("Inactive", "Inactive")]


def timezones():
    try:
        from zoneinfo import available_timezones

        return sorted(tz for tz in available_timezones() if "/" in tz and not tz.startswith(("Etc/", "SystemV/"))) + ["UTC"]
    except Exception:
        return ["UTC"]


class GeneralSettingsSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(max_length=150)
    timezone = serializers.CharField(max_length=64)
    date_format = serializers.ChoiceField(choices=DATE_FORMATS)
    time_format = serializers.ChoiceField(choices=TIME_FORMATS)
    currency = serializers.ChoiceField(choices=CURRENCIES)
    language = serializers.ChoiceField(choices=LANGUAGES)

    class Meta:
        model = CompanySettings
        fields = ["company_name", "tagline", "timezone", "date_format", "time_format", "currency", "language"]

    def validate_timezone(self, value):
        if value not in timezones():
            raise serializers.ValidationError("Choose a valid time zone.")
        return value


class CompanyDetailsSerializer(serializers.ModelSerializer):
    legal_name = serializers.CharField(max_length=200)
    address = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.RegexField(r"^[0-9+\-() ]{6,20}$", error_messages={"invalid": "Enter a valid phone number."})

    class Meta:
        model = CompanySettings
        fields = ["legal_name", "address", "email", "phone", "website", "gstin"]

    def validate_gstin(self, value):
        value = (value or "").strip().upper()
        if value and len(value) != 15:
            raise serializers.ValidationError("A GSTIN has 15 characters.")
        return value


class UserRowSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="effective_role")
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "email", "role", "status", "last_login"]

    def get_status(self, obj):
        return obj.status.capitalize()


class InviteUserSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this e-mail already exists.")
        return value


class UpdateUserSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    role = serializers.ChoiceField(choices=Role.choices, required=False)
    status = serializers.CharField(required=False)

    def validate_status(self, value):
        value = value.strip().lower()
        if value not in ("active", "inactive"):
            raise serializers.ValidationError("Status must be Active or Inactive.")
        return value


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "message", "type", "created_at", "read", "link"]


class BackupSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupSettings
        fields = ["automatic", "retention_months"]


class AuditLogSerializer(serializers.ModelSerializer):
    time = serializers.DateTimeField(source="created_at")
    user = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["id", "time", "user", "action", "target"]

    def get_user(self, obj):
        return (obj.user.name or obj.user.username) if obj.user else "System"
