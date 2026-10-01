import logging

from django.conf import settings
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db.models import Q
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import LoginActivity, User
from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)

log = logging.getLogger(__name__)


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class LoginView(APIView):
    """POST {username, password} -> {access, refresh, user}. `username` may also be the e-mail address."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        login = data.validated_data["username"]
        password = data.validated_data["password"]

        match = User.objects.filter(Q(username__iexact=login) | Q(email__iexact=login)).first()
        user = authenticate(request, username=match.username, password=password) if match else None

        LoginActivity.objects.create(
            user=match,
            username_attempted=login[:254],
            success=bool(user),
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
        if not user:
            if match and not match.is_active and match.check_password(password):
                return Response({"detail": "This account has been deactivated. Contact your administrator."},
                                status=status.HTTP_403_FORBIDDEN)
            return Response({"detail": "Invalid username or password."}, status=status.HTTP_401_UNAUTHORIZED)

        from django.contrib.auth.models import update_last_login
        update_last_login(None, user)
        return Response({**tokens_for(user), "user": UserSerializer(user).data})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class LogoutView(APIView):
    """Blacklists the refresh token when the client sends one; the access token simply expires."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh") if hasattr(request.data, "get") else None
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # already expired / blacklisted: the user is logged out either way
        return Response(status=status.HTTP_204_NO_CONTENT)


class ForgotPasswordView(APIView):
    """Always answers the same way so the endpoint can't be used to discover accounts."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        data = ForgotPasswordSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=data.validated_data["email"], is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?uid={uid}&token={token}"
            try:
                send_mail(
                    "Reset your HIPA MASALA password",
                    f"Hello {user.name or user.username},\n\nUse this link to set a new password:\n{link}\n\n"
                    "If you did not ask for this, you can ignore this e-mail.",
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                )
            except Exception:
                log.exception("Could not send password reset e-mail")
                return Response({"detail": "The reset e-mail could not be sent. Please try again later."},
                                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"detail": "If an account exists for that e-mail, a reset link has been sent."})


def user_from_uid(uid):
    try:
        return User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        data = ResetPasswordSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = user_from_uid(data.validated_data.get("uid") or "")
        if not user or not default_token_generator.check_token(user, data.validated_data["token"]):
            return Response({"detail": "This reset link is invalid or has expired. Please request a new one."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            password_validation.validate_password(data.validated_data["password"], user)
        except DjangoValidationError as exc:
            return Response({"password": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(data.validated_data["password"])
        user.save(update_fields=["password", "updated_at"])
        return Response({"detail": "Your password has been reset. You can now sign in."})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = ChangePasswordSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        request.user.set_password(data.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])
        return Response({"detail": "Password changed."})
