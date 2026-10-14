import logging

from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from services import audit

from .permissions import ModulePermission

logger = logging.getLogger(__name__)


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


class HealthView(APIView):
    """
    GET /api/v1/health/: for uptime monitors. Open to everyone and tells nothing about the setup: 200 {"status": "ok"}
    when the server and its database answer, 503 when the database can't be reached.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        from django.db import connection

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            logger.exception("Health check: database unreachable")
            return Response({"status": "unavailable", "database": "unreachable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE,
                            headers={"Cache-Control": "no-store"})
        return Response({"status": "ok", "database": "ok"}, headers={"Cache-Control": "no-store"})


class DeleteRecordView(APIView):
    """DELETE /api/v1/records/<kind>/<id>/: a Super Admin deletes a wrong entry in any module (services/deletion.py)."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, kind, pk):
        from apps.core.roles import has_any_role
        from services.deletion import delete_record

        if not has_any_role(request.user, ["admin"]):
            raise PermissionDenied("Only a Super Admin can delete records.")
        label, _module, what = delete_record(kind, pk)
        audit.record(request, f"Deleted {what}", label)
        return Response(status=status.HTTP_204_NO_CONTENT)
