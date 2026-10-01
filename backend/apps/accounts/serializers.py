from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="effective_role", read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "email", "username", "role"]


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
