from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="effective_role", read_only=True)
    # Main role plus extra roles; the web app shows menus and buttons for all of them
    roles = serializers.ListField(source="all_roles", child=serializers.CharField(), read_only=True)
    # Attendance permission codes, so the web app shows only the Attendance tabs the person may use
    attendance_permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "email", "username", "role", "roles", "attendance_permissions", "is_owner"]

    def get_attendance_permissions(self, obj):
        from apps.attendance import permissions as attendance_perms

        return attendance_perms.granted(obj)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField(required=False, allow_blank=True)
    token = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": ["Your current password is incorrect."]})
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError({"new_password": ["Choose a password different from the current one."]})
        try:
            password_validation.validate_password(attrs["new_password"], user)
        except Exception as exc:  # django ValidationError -> field error
            raise serializers.ValidationError({"new_password": list(getattr(exc, "messages", [str(exc)]))})
        return attrs
