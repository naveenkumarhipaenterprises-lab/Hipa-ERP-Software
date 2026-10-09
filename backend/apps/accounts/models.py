from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.roles import Role


class User(AbstractUser):
    """A portal user. `role` decides which modules they can open and change."""

    email = models.EmailField("email address", unique=True)
    name = models.CharField("full name", max_length=150)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SALES, db_index=True)
    # More team roles on top of `role`, for people who work in several areas (e.g. Purchase + Inventory).
    # Access is the union of all their roles. Super Admin is only ever the main role.
    extra_roles = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Sign-in tokens carry this number; raising it cancels every token issued before (logout, password change/reset)
    token_version = models.PositiveIntegerField(default=0, editable=False)

    REQUIRED_FIELDS = ["email", "name"]

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name or self.username} ({self.get_role_display()})"

    @property
    def effective_role(self):
        return Role.ADMIN if self.is_superuser else self.role

    @property
    def is_owner(self):
        """The owner (a Django superuser) is the only one who may create or change Super Admin accounts."""
        return self.is_superuser

    @property
    def all_roles(self):
        """The main role first, then any extra roles (valid, distinct, never Super Admin)."""
        main = self.effective_role
        extras = [r for r in (self.extra_roles or []) if r in Role.values and r not in (Role.ADMIN, main)]
        return [main, *dict.fromkeys(extras)]

    def save(self, *args, **kwargs):
        self.extra_roles = [r for r in dict.fromkeys(self.extra_roles or []) if r in Role.values and r not in (Role.ADMIN, self.role)]
        if self.is_superuser:  # superusers act as admins; store that too, so the database doesn't say otherwise
            self.role = Role.ADMIN
        super().save(*args, **kwargs)

    def revoke_tokens(self):
        """Signs the user out on every device: tokens issued before this call stop working."""
        User.objects.filter(pk=self.pk).update(token_version=models.F("token_version") + 1)
        self.refresh_from_db(fields=["token_version"])

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
