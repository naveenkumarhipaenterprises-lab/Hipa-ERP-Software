from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated

from .permissions import ModulePermission


class ModuleMixin:
    """Every business endpoint: signed in + role allowed for `module` (and `write_module` for changes)."""

    module = None
    write_module = None
    permission_classes = [IsAuthenticated, ModulePermission]


class ModuleAPIView(ModuleMixin, GenericAPIView):
    def paginated(self, queryset, row):
        """{ count, next, previous, results } with `row(obj)` building each result."""
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([row(obj) for obj in page])

    def param(self, name, default=""):
        return (self.request.query_params.get(name) or default).strip()

    def int_param(self, name):
        """Optional numeric filter (e.g. ?product=3); anything else is a validation error."""
        value = self.param(name)
        if not value:
            return None
        if not value.isdigit():
            raise ValidationError({name: ["Must be a number."]})
        return int(value)
