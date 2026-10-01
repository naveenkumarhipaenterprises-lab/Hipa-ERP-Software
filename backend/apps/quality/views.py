from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.ai_assistant import insights
from apps.core import periods
from apps.core.files import csv_response
from apps.core.metrics import choices, kpi, ratio_pct, resolve_choice
from apps.core.views import ModuleAPIView
from apps.production.models import ProductionBatch
from services import audit, notifications

from .models import Certification, QualityAudit, QualityStandard, QualityTest

R = QualityTest.Result


def test_row(t):
    return {"id": t.id, "batch_number": t.batch.batch_number, "product": t.batch.product.name, "test_date": t.test_date,
            "parameters": t.parameters, "result": t.get_result_display(), "status": t.status, "notes": t.notes or None}


def certification_status(c, today):
    if not c.valid_until:
        return None
    if c.valid_until < today:
        return "Expired"
    if c.valid_until <= today + timedelta(days=60):
        return "Expiring Soon"
    return "Active"


def test_stats(qs):
    total = qs.count()
    passed = qs.filter(result=R.PASS).count()
    hours = [h for h in (t.testing_hours for t in qs.select_related("batch")) if h is not None]
    return {
        "tested": qs.values("batch").distinct().count(),
        "pass_rate": ratio_pct(passed, total),
        "failed": qs.filter(result=R.FAIL).count(),
        "avg_hours": round(sum(hours) / len(hours), 1) if hours else None,
    }


class QualityView(ModuleAPIView):
    module = "quality"


class OverviewView(QualityView):
    def get(self, request):
        cur, prev = periods.resolve(self.param("range"))
        now = test_stats(QualityTest.objects.filter(test_date__range=(cur.start, cur.end)))
        before = test_stats(QualityTest.objects.filter(test_date__range=(prev.start, prev.end)))
        per_product = (QualityTest.objects.filter(test_date__range=(cur.start, cur.end))
                       .values("batch__product__name")
                       .annotate(batches=Count("batch", distinct=True), n=Count("id"), passed=Count("id", filter=Q(result=R.PASS)))
                       .order_by("batch__product__name"))
        today = periods.today()
        return Response({
            "kpis": {
                "batches_tested": kpi(now["tested"], before["tested"]),
                "pass_rate_pct": kpi(now["pass_rate"], before["pass_rate"]),
                "failed_batches": kpi(now["failed"], before["failed"]),
                "avg_testing_hours": kpi(now["avg_hours"], before["avg_hours"]),
            },
            "product_quality": [{"name": r["batch__product__name"], "batches": r["batches"], "pass_rate_pct": ratio_pct(r["passed"], r["n"])}
                                for r in per_product],
            "certifications": [{"id": c.id, "name": c.name, "detail": c.detail or None, "valid_until": c.valid_until,
                                "status": certification_status(c, today)} for c in Certification.objects.all()],
            "insights": insights.items_block("quality"),
        })


class TrendView(QualityView):
    def get(self, request):
        cur, _ = periods.resolve(self.param("range"))
        granularity = periods.parse_choice(self.param("granularity"), ["daily", "weekly"], "granularity", "daily")
        tests = list(QualityTest.objects.filter(test_date__range=(cur.start, cur.end)).values("test_date", "result", "batch_id"))
        if not tests:
            return Response([])
        step = 1 if granularity == "daily" else 7
        points, day = [], cur.start
        while day <= cur.end:
            last = min(day + timedelta(days=step - 1), cur.end)
            bucket = [t for t in tests if day <= t["test_date"] <= last]
            points.append({
                "label": day.strftime("%d %b") if step == 1 else f"{day:%d %b}–{last:%d %b}",
                "batches": len({t["batch_id"] for t in bucket}),
                "pass_rate_pct": ratio_pct(sum(t["result"] == R.PASS for t in bucket), len(bucket)),
            })
            day = last + timedelta(days=1)
        return Response(points)


class OptionsView(QualityView):
    def get(self, request):
        pending = (ProductionBatch.objects.select_related("product")
                   .filter(stage__in=[ProductionBatch.Stage.PACKAGING, ProductionBatch.Stage.COMPLETED, ProductionBatch.Stage.HOLD])
                   .exclude(quality_tests__result=R.PASS).exclude(quality_tests__result=R.FAIL)
                   .order_by("-start_date"))
        return Response({
            "pending_batches": [{"id": b.id, "batch_number": b.batch_number, "product": b.product.name} for b in pending],
            "results": choices(R),
            "audit_types": choices(QualityAudit.AuditType),
        })


def filtered_tests(params, period=None):
    qs = QualityTest.objects.select_related("batch__product")
    q = (params.get("search") or "").strip()
    if q:
        qs = qs.filter(Q(batch__batch_number__icontains=q) | Q(batch__product__name__icontains=q) | Q(parameters__icontains=q))
    result = resolve_choice(R, params.get("result"), "result")
    if result:
        qs = qs.filter(result=result)
    if period:
        qs = qs.filter(test_date__range=(period.start, period.end))
    return qs


class TestsView(QualityView):
    def get(self, request):
        return self.paginated(filtered_tests(request.query_params), test_row)

    def post(self, request):
        d = request.data
        errors = {}
        batch = ProductionBatch.objects.select_related("product").filter(pk=d.get("batch_id")).first() if str(d.get("batch_id", "")).isdigit() else None
        if not batch:
            errors["batch_id"] = ["Choose a batch."]
        test_date = parse_date(str(d.get("test_date") or ""))
        if not test_date:
            errors["test_date"] = ["Enter the test date (YYYY-MM-DD)."]
        elif test_date > periods.today():
            errors["test_date"] = ["The test date can't be in the future."]
        elif batch and test_date < batch.start_date:
            errors["test_date"] = ["The test date can't be before the batch started."]
        try:
            result = resolve_choice(R, d.get("result"), "result")
            if not result:
                errors["result"] = ["Choose a result."]
        except ValidationError as exc:
            errors.update(exc.detail)
        parameters = str(d.get("parameters") or "").strip()
        if not parameters:
            errors["parameters"] = ["Describe what was tested."]
        if errors:
            raise ValidationError(errors)

        with transaction.atomic():
            test = QualityTest.objects.create(batch=batch, test_date=test_date, result=result, parameters=parameters,
                                              notes=str(d.get("notes") or "").strip(), tested_by=request.user)
            # A failed or held batch that is still in production is put on hold
            if result in (R.FAIL, R.HOLD) and batch.stage != ProductionBatch.Stage.COMPLETED:
                batch.stage = ProductionBatch.Stage.HOLD
                batch.save(update_fields=["stage", "updated_at"])
        audit.record(request, f"Recorded quality test ({test.get_result_display()})", batch.batch_number)
        if result in (R.FAIL, R.HOLD):
            notifications.notify("quality_failures", f"Batch {batch.batch_number}: {test.get_result_display()}",
                                 f"{batch.product.name}. {parameters[:150]}", type="error", link="/quality")
        return Response(test_row(test), status=status.HTTP_201_CREATED)


class StandardsView(QualityView):
    def get(self, request):
        return Response([
            {"id": s.id, "parameter": s.parameter, "limit": s.limit, "applies_to": s.product.name if s.product else "All products"}
            for s in QualityStandard.objects.select_related("product")
        ])


class AuditsView(QualityView):
    def post(self, request):
        d = request.data
        errors = {}
        try:
            audit_type = resolve_choice(QualityAudit.AuditType, d.get("audit_type"), "audit_type")
            if not audit_type:
                errors["audit_type"] = ["Choose the audit type."]
        except ValidationError as exc:
            errors.update(exc.detail)
        day = parse_date(str(d.get("date") or ""))
        if not day:
            errors["date"] = ["Enter the audit date (YYYY-MM-DD)."]
        elif day < periods.today():
            errors["date"] = ["An audit can't be scheduled in the past."]
        if errors:
            raise ValidationError(errors)
        a = QualityAudit.objects.create(audit_type=audit_type, date=day, auditor=str(d.get("auditor") or "").strip()[:120],
                                        created_by=request.user)
        audit.record(request, "Scheduled quality audit", f"{a.get_audit_type_display()} on {day:%d %b %Y}")
        return Response({"id": a.id, "audit_type": a.audit_type, "date": a.date, "auditor": a.auditor or None,
                         "status": a.get_status_display()}, status=status.HTTP_201_CREATED)


class ReportView(QualityView):
    def get(self, request):
        cur, _ = periods.resolve(self.param("range"))
        rows = ([t.batch.batch_number, t.batch.product.name, t.test_date, t.parameters, t.get_result_display(), t.status, t.notes]
                for t in filtered_tests(request.query_params, cur).order_by("test_date", "id"))
        return csv_response(f"hipa-quality-{self.param('range') or 'this_month'}-{periods.today():%Y%m%d}.csv",
                            ["Batch", "Product", "Test date", "Parameters", "Result", "Status", "Notes"], rows)
