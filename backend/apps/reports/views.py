import logging

from django.db.models import BooleanField, ExpressionWrapper, Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.core import periods
from apps.core.metrics import kpi
from apps.core.roles import can_read, role_of
from apps.core.views import ModuleAPIView
from apps.customers.models import Customer
from apps.sales import selectors
from services import audit, notifications
from services.exporters import MIME, export

from .builders import MODULE_FOR_TYPE, build
from .models import Report

log = logging.getLogger(__name__)


def check_type(user, report_type):
    if report_type not in MODULE_FOR_TYPE:
        raise ValidationError({"type": [f"Unknown report type. Use one of: {', '.join(MODULE_FOR_TYPE)}."]})
    if not can_read(user, MODULE_FOR_TYPE[report_type]):
        raise PermissionDenied("Your role can't view this report.")


def check_format(fmt):
    if fmt not in MIME:
        raise ValidationError({"format": ["Use pdf, xlsx or csv."]})
    return fmt


def file_name(report_type, range_key, fmt):
    return f"hipa-{report_type.replace('_', '-')}-report-{range_key}-{periods.today():%Y%m%d}.{fmt}"


def report_row(r, stored=None):
    stored = r.content is not None if stored is None else stored
    return {"id": r.id, "name": r.name, "type": r.type, "range_label": r.range_label, "format": r.format,
            "created_at": r.created_at, "created_by": (r.created_by.name or r.created_by.username) if r.created_by else None,
            "status": r.get_status_display(), "download_available": r.status == Report.Status.READY and (stored or bool(r.file))}


def visible_types(user):
    return [t for t, module in MODULE_FOR_TYPE.items() if can_read(user, module)]


class ReportsView(ModuleAPIView):
    module = "reports"


class OverviewView(ReportsView):
    def get(self, request):
        cur, prev = periods.resolve(self.param("range"))
        k = {}
        if can_read(request.user, "sales"):
            now, before = selectors.totals(cur.start, cur.end), selectors.totals(prev.start, prev.end)
            k["revenue"] = kpi(now["sales"], before["sales"])
            k["orders"] = kpi(now["orders"], before["orders"])
            k["products_sold_kg"] = kpi(now["kg"], before["kg"])
        if can_read(request.user, "customers"):
            k["customers"] = kpi(Customer.objects.filter(created_at__lte=periods.end_of(cur.end)).count(),
                                 Customer.objects.filter(created_at__lte=periods.end_of(prev.end)).count())
        return Response({"kpis": k})


class PreviewView(ReportsView):
    def get(self, request):
        report_type = self.param("type")
        check_type(request.user, report_type)
        data, _period = build(report_type, self.param("range"), request.user)
        return Response(data)


class ExportView(ReportsView):
    def get(self, request):
        report_type, range_key = self.param("type"), self.param("range") or "this_month"
        check_type(request.user, report_type)
        fmt = check_format(self.param("format") or "pdf")
        data, _period = build(report_type, range_key, request.user)
        content, mime = export(data, fmt)
        response = HttpResponse(content, content_type=mime)
        response["Content-Disposition"] = f'attachment; filename="{file_name(report_type, range_key, fmt)}"'
        audit.record(request, "Exported report", f"{report_type} {range_key} {fmt}")
        return response


class ReportListView(ReportsView):
    def get(self, request):
        # The file bytes aren't loaded for the list; only whether they exist
        qs = (Report.objects.select_related("created_by").defer("content").filter(type__in=visible_types(request.user))
              .annotate(stored=ExpressionWrapper(Q(content__isnull=False), output_field=BooleanField())))
        # Everyone sees their own reports; admins and management see all
        if role_of(request.user) not in ("admin", "management"):
            qs = qs.filter(created_by=request.user)
        t = self.param("type")
        if t:
            qs = qs.filter(type=t)
        return self.paginated(qs, lambda r: report_row(r, r.stored))

    def post(self, request):
        report_type = str(request.data.get("type") or "")
        range_key = str(request.data.get("range") or "this_month")
        check_type(request.user, report_type)
        fmt = check_format(str(request.data.get("format") or "pdf"))
        data, period = build(report_type, range_key, request.user)
        report = Report.objects.create(name=f"{Report.Type(report_type).label} — {period.label}", type=report_type, range=range_key,
                                       range_label=f"{period.label} ({period.start:%d %b %Y} – {period.end:%d %b %Y})",
                                       format=fmt, created_by=request.user)
        try:
            content, _mime = export(data, fmt)
            report.content = content
            report.status = Report.Status.READY
        except Exception as exc:
            log.exception("Report generation failed")
            report.status = Report.Status.FAILED
            report.error = str(exc)[:500]
        report.save()
        audit.record(request, "Generated report", report.name)
        if report.status == Report.Status.READY:
            notifications.notify("report_ready", "Report ready", report.name, type="success", link="/reports", users=[request.user])
        return Response(report_row(report), status=status.HTTP_201_CREATED)


class DownloadView(ReportsView):
    def get(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        check_type(request.user, report.type)
        if role_of(request.user) not in ("admin", "management") and report.created_by_id != request.user.id:
            raise NotFound("Report not found.")
        if report.status != Report.Status.READY or (report.content is None and not report.file):
            raise NotFound("This report file is not available.")
        if report.content is not None:
            response = HttpResponse(bytes(report.content), content_type=MIME[report.format])
            name = f"hipa-{report.type.replace('_', '-')}-report-{report.range}-{report.created_at:%Y%m%d}.{report.format}"
            response["Content-Disposition"] = f'attachment; filename="{name}"'
            return response
        try:  # generated before reports were kept in the database
            handle = report.file.open("rb")
        except FileNotFoundError:
            raise NotFound("This report file is no longer on the server.")
        name = report.file.name.rsplit("/", 1)[-1]
        return FileResponse(handle, as_attachment=True, filename=name, content_type=MIME[report.format])
