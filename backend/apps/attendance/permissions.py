"""Per-user Attendance permissions ("attendance.<code>"), enforced on the server. A Super Admin has all of them."""
from django.contrib.auth.models import Permission
from rest_framework.exceptions import PermissionDenied

from apps.core.roles import Role, role_of

from .models import PERMISSIONS

CODES = [code for code, _label in PERMISSIONS]
LABELS = dict(PERMISSIONS)


def has(user, code):
    return role_of(user) == Role.ADMIN or user.has_perm(f"attendance.{code}")


def require(user, code, message="You don't have permission to do this in Attendance."):
    if not has(user, code):
        raise PermissionDenied(message)


def flags(user):
    return {code: has(user, code) for code in CODES}


def granted(user):
    """Codes stored for this user (a Super Admin implicitly has all)."""
    if role_of(user) == Role.ADMIN:
        return list(CODES)
    # .all() so a list prefetched with user_permissions__content_type costs no extra query per user
    return sorted(p.codename for p in user.user_permissions.all()
                  if p.content_type.app_label == "attendance" and p.codename in CODES)


def set_granted(user, codes):
    """Replaces the user's Attendance permissions with `codes`."""
    all_perms = Permission.objects.filter(content_type__app_label="attendance", codename__in=CODES)
    user.user_permissions.remove(*all_perms)
    user.user_permissions.add(*[p for p in all_perms if p.codename in set(codes)])
    for cache in ("_perm_cache", "_user_perm_cache"):
        user.__dict__.pop(cache, None)
