from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.roles import Role


class User(AbstractUser):
    """A portal user. `role` decides which modules they can open and change."""

    email = models.EmailField("email address", unique=True)
    name = models.CharField("full name", max_length=150)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SALES, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ["email", "name"]

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name or self.username} ({self.get_role_display()})"

    @property
    def effective_role(self):
        return Role.ADMIN if self.is_superuser else self.role

    @property
    def status(self):
        if not self.is_active:
            return "inactive"
        if not self.has_usable_password():
            return "invited"
        return "active"


class LoginActivity(models.Model):
    """Every login attempt, successful or not (shown in Settings → Security)."""

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="login_activity")
    username_attempted = models.CharField(max_length=254)
    success = models.BooleanField(default=False)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "login activity"

    def __str__(self):
        return f"{self.username_attempted} {'ok' if self.success else 'failed'} {self.created_at:%Y-%m-%d %H:%M}"
