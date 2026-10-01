from rest_framework.permissions import SAFE_METHODS, BasePermission

from .roles import can_read, can_write


class ModulePermission(BasePermission):
    """
    Reads (GET/HEAD/OPTIONS) need view access to `view.module`;
    writes need change access to `view.write_module` (defaults to `view.module`).
    """

    message = "You don't have access to this module."

    def has_permission(self, request, view):
        user = request.user
        module = getattr(view, "module", None)
        if not module or not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return can_read(user, module)
        if not can_write(user, getattr(view, "write_module", None) or module):
            self.message = (
                "Your role can view this module but not change it." if can_read(user, module) else self.message
            )
            return False
        return True
