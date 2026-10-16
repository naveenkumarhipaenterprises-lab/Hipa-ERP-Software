import re
from datetime import timedelta

from django.db import transaction
from django.http import HttpResponse
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apps.ai_assistant import insights
from apps.core import parsing, periods
from apps.core.files import csv_response
from apps.core.metrics import choices, kpi, label_choices, ratio_pct, resolve_choice
from apps.core.views import ModuleAPIView
from apps.inventory.models import Product
from apps.purchase.models import GoodsReceipt, RawMaterial
from services import audit, notifications

from .models import Certification, QualityAudit, QualityStandard, QualityTest

R = QualityTest.Result
ITEM_NAME = Coalesce("product__name", "material__name")
MAX_READINGS = 50
NUMBER = re.compile(r"^-?(\d+(\.\d+)?|\.\d+)$")  # 8, 8.5, -2.25, .5


def test_row(t):
    grn = t.goods_receipt
    return {"id": t.id, "batch_number": t.batch_number or None, "product": t.item.name,
            "item_type": "product" if t.product_id else "material", "goods_receipt_id": t.goods_receipt_id,
            "grn_number": grn.grn_number if grn else None, "test_date": t.test_date, "parameters": t.parameters,
            "readings": t.readings, "result": t.get_result_display(), "status": t.status, "notes": t.notes or None}


def certification_status(c, today):
    """Pending Verification / Suspended when set; otherwise from the expiry date (Expiring Soon = within 60 days)."""
    if c.status != Certification.Status.ACTIVE:
        return c.get_status_display()
    if not c.valid_until:
        return "Active"
    if c.valid_until < today:
        return "Expired"
    if c.valid_until <= today + timedelta(days=60):
        return "Expiring Soon"
    return "Active"


def certification_row(c, today=None):
    return {"id": c.id, "name": c.name, "detail": c.detail or None, "issuing_authority": c.issuing_authority or None,
            "certificate_number": c.certificate_number or None, "category": c.get_category_display() or None,
            "category_value": c.category or None, "issue_date": c.issue_date, "valid_until": c.valid_until,
            "status": certification_status(c, today or periods.today()), "status_value": c.status, "notes": c.notes or None,
            "document": {"name": c.document_name, "type": c.document_type, "size": c.document_size} if c.document_name else None,
            "updated_at": c.updated_at}


def test_stats(qs):
    total = qs.count()
    passed = qs.filter(result=R.PASS).count()
    hours = [h for h in (t.testing_hours for t in qs.select_related("goods_receipt")) if h is not None]
    return {
        "tested": total,  # each test checks one lot
        "pass_rate": ratio_pct(passed, total),
        "failed": qs.filter(result=R.FAIL).count(),
        "avg_hours": round(sum(hours) / len(hours), 1) if hours else None,
    }


def read_readings(raw, errors):
    """
    [{parameter, value}] -> the cleaned rows. Every row needs a parameter name and a numeric value (decimals allowed);
    nothing invalid is turned into 0. Problems go in errors["readings"], one message per problem.
    """
    if not isinstance(raw, list) or not raw:
        errors["readings"] = ["Add at least one parameter and its value."]
        return []
    if len(raw) > MAX_READINGS:
        errors["readings"] = [f"Add at most {MAX_READINGS} parameters."]
        return []
    rows, seen, problems = [], set(), []
    for i, row in enumerate(raw, 1):
        row = row if isinstance(row, dict) else {}
        name = str(row.get("parameter") or "").strip()
        value = "" if row.get("value") is None or isinstance(row.get("value"), bool) else str(row.get("value")).strip()
        if not name:
            problems.append(f"Row {i}: enter the parameter name.")
        elif len(name) > 120:
            problems.append(f"Row {i}: the parameter name can be at most 120 characters.")
        elif name.lower() in seen:
            problems.append(f"Row {i}: {name} is listed twice.")
        if not value:
            problems.append(f"Row {i}: enter the value.")
        elif len(value) > 20 or not NUMBER.match(value):
            problems.append(f"Row {i}: the value must be a number, e.g. 8.5.")
        seen.add(name.lower())
        rows.append({"parameter": name, "value": value})
    if problems:
        errors["readings"] = problems
    return rows


def readings_text(readings):
    """The pairs as one line ("Moisture: 8.5; Ash: 3.2"), kept in `parameters` for search, exports and reports."""
    return "; ".join(f"{r['parameter']}: {r['value']}" for r in readings)


def lot_label(test):
    grn = test.goods_receipt
    return " ".join(x for x in (test.item.name, test.batch_number, f"({grn.grn_number})" if grn else "") if x)


class QualityView(ModuleAPIView):
    module = "quality"


class OverviewView(QualityView):
    def get(self, request):
        cur, prev = periods.resolve(self.param("range"))
        now = test_stats(QualityTest.objects.filter(test_date__range=(cur.start, cur.end)))
        before = test_stats(QualityTest.objects.filter(test_date__range=(prev.start, prev.end)))
        per_product = (QualityTest.objects.filter(test_date__range=(cur.start, cur.end))
                       .annotate(item=ITEM_NAME).values("item")
                       .annotate(n=Count("id"), passed=Count("id", filter=Q(result=R.PASS)))
                       .order_by("item"))
        today = periods.today()
        return Response({
            "kpis": {
                "batches_tested": kpi(now["tested"], before["tested"]),
                "pass_rate_pct": kpi(now["pass_rate"], before["pass_rate"]),
                "failed_batches": kpi(now["failed"], before["failed"]),
                "avg_testing_hours": kpi(now["avg_hours"], before["avg_hours"]),
            },
            "product_quality": [{"name": r["item"], "batches": r["n"], "pass_rate_pct": ratio_pct(r["passed"], r["n"])}
                                for r in per_product],
            "certifications": [certification_row(c, today) for c in certifications()],
            "insights": insights.items_block("quality"),
        })


class TrendView(QualityView):
    def get(self, request):
        cur, _ = periods.resolve(self.param("range"))
        granularity = periods.parse_choice(self.param("granularity"), ["daily", "weekly"], "granularity", "daily")
        tests = list(QualityTest.objects.filter(test_date__range=(cur.start, cur.end)).values("test_date", "result", "id"))
        if not tests:
            return Response([])
        step = 1 if granularity == "daily" else 7
        points, day = [], cur.start
        while day <= cur.end:
            last = min(day + timedelta(days=step - 1), cur.end)
            bucket = [t for t in tests if day <= t["test_date"] <= last]
            points.append({
                "label": day.strftime("%d %b") if step == 1 else f"{day:%d %b}–{last:%d %b}",
                "batches": len(bucket),
                "pass_rate_pct": ratio_pct(sum(t["result"] == R.PASS for t in bucket), len(bucket)),
            })
            day = last + timedelta(days=1)
        return Response(points)


def receipt_option(g):
    return {"id": g.id, "grn_number": g.grn_number, "item": g.purchase.item_name, "item_type": g.purchase.item_type,
            "supplier": g.purchase.supplier.name, "received_date": g.received_date, "quality_status": g.get_quality_status_display()}


class OptionsView(QualityView):
    MAX_RECEIPTS = 500

    def get(self, request):
        Q_ = GoodsReceipt.QualityStatus
        receipts = GoodsReceipt.objects.select_related("purchase__supplier", "purchase__material", "purchase__product")
        waiting = Q(quality_status__in=(Q_.PENDING, Q_.ON_HOLD))
        pending = receipts.filter(waiting).order_by("-received_date", "-id")
        # Every real GRN can be tested, also one recorded as Passed / Failed at receipt: awaiting inspection first
        everything = receipts.annotate(waiting=Case(When(waiting, then=Value(0)), default=Value(1), output_field=IntegerField())
                                       ).order_by("waiting", "-received_date", "-id")[:self.MAX_RECEIPTS]
        return Response({
            "pending_receipts": [receipt_option(g) for g in pending],
            "goods_receipts": [receipt_option(g) for g in everything],
            "products": list(Product.objects.filter(is_active=True).values("id", "name")),
            "materials": list(RawMaterial.objects.filter(status=RawMaterial.Status.ACTIVE).values("id", "name")),
            "results": choices(R),
            "audit_types": choices(QualityAudit.AuditType),
            "audit_statuses": label_choices(QualityAudit.Status),
            "certification_categories": choices(Certification.Category),
            "certification_statuses": choices(Certification.Status),
        })


def filtered_tests(params, period=None):
    qs = QualityTest.objects.select_related("product", "material", "goods_receipt")
    q = (params.get("search") or "").strip()
    if q:
        qs = qs.filter(Q(batch_number__icontains=q) | Q(product__name__icontains=q) | Q(material__name__icontains=q) |
                       Q(goods_receipt__grn_number__icontains=q) | Q(parameters__icontains=q))
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
        grn, product, material = None, None, None
        if d.get("goods_receipt_id") not in (None, ""):
            grn = parsing.record(d, "goods_receipt_id", GoodsReceipt.objects.select_related("purchase__material", "purchase__product"),
                                 errors, message="Choose a goods receipt.")
            if grn:
                product, material = grn.purchase.product, grn.purchase.material
        elif d.get("product_id") not in (None, ""):
            product = parsing.record(d, "product_id", Product.objects.all(), errors, message="Choose a product.")
        else:
            material = parsing.record(d, "material_id", RawMaterial.objects.all(), errors,
                                      message="Choose a goods receipt, a product or a raw material.")
        batch_number = parsing.text(d, "batch_number", 40)
        test_date = parse_date(str(d.get("test_date") or ""))
        if not test_date:
            errors["test_date"] = ["Enter the test date (YYYY-MM-DD)."]
        elif test_date > periods.today():
            errors["test_date"] = ["The test date can't be in the future."]
        elif grn and test_date < grn.received_date:
            errors["test_date"] = ["The test date can't be before the goods were received."]
        try:
            result = resolve_choice(R, d.get("result"), "result")
            if not result:
                errors["result"] = ["Choose a result."]
        except ValidationError as exc:
            errors.update(exc.detail)
        if "readings" in d:  # Parameter + Value rows
            readings = read_readings(d.get("readings"), errors)
            parameters = readings_text(readings)
        else:  # a single text, as before
            readings, parameters = [], str(d.get("parameters") or "").strip()
            if not parameters:
                errors["parameters"] = ["Describe what was tested."]
        if errors:
            raise ValidationError(errors)

        with transaction.atomic():
            test = QualityTest.objects.create(product=product, material=material, goods_receipt=grn, batch_number=batch_number,
                                              test_date=test_date, result=result, parameters=parameters, readings=readings,
                                              notes=str(d.get("notes") or "").strip(), tested_by=request.user)
            # The goods receipt's inspection status follows its latest test
            if grn:
                grn.quality_status = QualityTest.GRN_STATUS_FOR_RESULT[result]
                grn.save(update_fields=["quality_status"])
        lot = " ".join(x for x in (test.item.name, batch_number, f"({grn.grn_number})" if grn else "") if x)
        audit.record(request, f"Recorded quality test ({test.get_result_display()})", lot)
        if result in (R.FAIL, R.HOLD):
            notifications.notify("quality_failures", f"{lot}: {test.get_result_display()}", parameters[:200], type="error",
                                 link="/quality")
        return Response(test_row(test), status=status.HTTP_201_CREATED)


class TestDetailView(QualityView):
    def patch(self, request, pk):
        """PATCH {readings}: changes only the Parameter + Value rows; item, lot, dates, result and notes stay as recorded."""
        errors = {}
        readings = read_readings(request.data.get("readings"), errors)
        if errors:
            raise ValidationError(errors)
        test = get_object_or_404(QualityTest.objects.select_related("product", "material", "goods_receipt"), pk=pk)
        test.readings, test.parameters = readings, readings_text(readings)
        test.save(update_fields=["readings", "parameters"])
        audit.record(request, "Edited quality test parameters", lot_label(test))
        return Response(test_row(test))


def standard_row(s):
    return {"id": s.id, "parameter": s.parameter, "limit": s.limit, "product_id": s.product_id,
            "applies_to": s.product.name if s.product else "All products"}


def read_standard(d, current=None):
    """A parameter is set once per product, and once for all products."""
    errors = {}
    parameter = parsing.text(d, "parameter", 120, required=True, errors=errors, label="parameter")
    limit = parsing.text(d, "limit", 120, required=True, errors=errors, label="limit")
    for field, label in (("parameter", "parameter"), ("limit", "limit")):
        if len(str(d.get(field) or "").strip()) > 120:
            errors[field] = [f"The {label} can be at most 120 characters."]
    product = parsing.record(d, "product_id", Product.objects.all(), errors, required=False, message="Choose a valid product.")
    if parameter and not errors:
        clash = QualityStandard.objects.filter(parameter__iexact=parameter, product=product)
        if current is not None:
            clash = clash.exclude(pk=current.pk)
        if clash.exists():
            errors["parameter"] = [f"{parameter} already has a limit for {product.name if product else 'all products'}. Edit that one."]
    if errors:
        raise ValidationError(errors)
    return {"parameter": parameter, "limit": limit, "product": product}


class StandardsView(QualityView):
    """GET: the acceptance limits. POST {parameter, limit, product_id?}: a new one (no product = all products)."""

    def get(self, request):
        return Response([standard_row(s) for s in QualityStandard.objects.select_related("product")])

    def post(self, request):
        s = QualityStandard.objects.create(**read_standard(request.data))
        audit.record(request, "Added quality standard", f"{s.parameter}: {s.limit}")
        return Response(standard_row(s), status=status.HTTP_201_CREATED)


class StandardDetailView(QualityView):
    def patch(self, request, pk):
        """Fields not sent keep their value."""
        s = get_object_or_404(QualityStandard.objects.select_related("product"), pk=pk)
        current = {"parameter": s.parameter, "limit": s.limit, "product_id": s.product_id or ""}
        for k, v in read_standard({**current, **{k: request.data.get(k) for k in current if k in request.data}}, s).items():
            setattr(s, k, v)
        s.save()
        audit.record(request, "Edited quality standard", f"{s.parameter}: {s.limit}")
        return Response(standard_row(s))


def audit_row(a):
    return {"id": a.id, "audit_type": a.get_audit_type_display(), "date": a.date, "auditor": a.auditor or None,
            "status": a.get_status_display(), "findings": a.findings or None,
            "can_update": a.status == QualityAudit.Status.SCHEDULED}


class AuditsView(QualityView):
    def get(self, request):
        qs = QualityAudit.objects.order_by("-date", "-id")
        st = resolve_choice(QualityAudit.Status, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        return self.paginated(qs, audit_row)

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
        return Response(audit_row(a), status=status.HTTP_201_CREATED)


class AuditStatusView(QualityView):
    """POST {status: completed, findings} or {status: cancelled}. Only scheduled audits change."""

    def post(self, request, pk):
        AS = QualityAudit.Status
        d, errors = request.data, {}
        with transaction.atomic():
            a = get_object_or_404(QualityAudit.objects.select_for_update(), pk=pk)
            if a.status != AS.SCHEDULED:
                raise ValidationError({"status": [f"A {a.get_status_display().lower()} audit can't be changed."]})
            new = parsing.choice(d, "status", AS, errors, message="Choose Completed or Cancelled.")
            if new == AS.SCHEDULED:
                errors["status"] = ["Choose Completed or Cancelled."]
            findings = parsing.text(d, "findings", 5000)
            if new == AS.COMPLETED:
                if not findings:
                    errors["findings"] = ["Write the audit findings."]
                if a.date > periods.today():
                    errors["status"] = [f"This audit is on {a.date:%d %b %Y}; it can be completed from that day."]
            if errors:
                raise ValidationError(errors)
            a.status = new
            if findings:
                a.findings = findings
            a.save(update_fields=["status", "findings"])
        audit.record(request, f"{a.get_status_display()} quality audit", f"{a.get_audit_type_display()} on {a.date:%d %b %Y}")
        return Response(audit_row(a))


class ReportView(QualityView):
    def get(self, request):
        cur, _ = periods.resolve(self.param("range"))
        rows = ([t.batch_number, t.item.name, t.goods_receipt.grn_number if t.goods_receipt else "", t.test_date, t.parameters,
                 t.get_result_display(), t.status, t.notes]
                for t in filtered_tests(request.query_params, cur).order_by("test_date", "id"))
        return csv_response(f"hipa-quality-{self.param('range') or 'this_month'}-{periods.today():%Y%m%d}.csv",
                            ["Lot / batch", "Item", "GRN", "Test date", "Parameters", "Result", "Status", "Notes"], rows)


# --- Certifications -------------------------------------------------------------------------------

MAX_DOCUMENT_BYTES = 4 * 1024 * 1024  # Vercel refuses requests over 4.5 MB
# Allowed certificate files: extension -> (MIME type, how the file starts)
DOCUMENT_TYPES = {".pdf": ("application/pdf", (b"%PDF-",)), ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
                  ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)), ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",))}


def certifications():
    """Without the stored documents (they are only read when someone opens one)."""
    return Certification.objects.defer("document")


def read_document(upload, errors):
    """(name, MIME type, bytes) of an uploaded certificate, or None with errors["document"] set."""
    name = (upload.name or "").strip()
    ext = name[name.rfind("."):].lower() if "." in name else ""
    if ext not in DOCUMENT_TYPES:
        errors["document"] = ["Upload a PDF, JPG, JPEG or PNG file."]
        return None
    if upload.size > MAX_DOCUMENT_BYTES:
        errors["document"] = ["The file can be at most 4 MB."]
        return None
    content = upload.read()
    if not content:
        errors["document"] = ["The file is empty."]
        return None
    mime, signatures = DOCUMENT_TYPES[ext]
    if not content.startswith(signatures):  # e.g. another kind of file renamed to .pdf
        errors["document"] = [f"This file is not a real {ext[1:].upper()} file."]
        return None
    return name[-150:], mime, content


def read_certification(d, files, current=None):
    errors = {}
    name = str(d.get("name") or "").strip()
    if not name:
        errors["name"] = ["Enter the certification name."]
    for field, label, limit in (("name", "name", 120), ("issuing_authority", "issuing authority", 150),
                                ("certificate_number", "certificate number", 80)):
        if len(str(d.get(field) or "").strip()) > limit:
            errors[field] = [f"The {label} can be at most {limit} characters."]
    category = parsing.choice(d, "category", Certification.Category, errors, required=False)
    cert_status = parsing.choice(d, "status", Certification.Status, errors, default=Certification.Status.ACTIVE)
    issue = parsing.date(d, "issue_date", errors, required=False, label="issue date")
    expiry = parsing.date(d, "valid_until", errors, required=False, label="expiry date")
    if issue and issue > periods.today():
        errors["issue_date"] = ["The issue date can't be in the future."]
    if issue and expiry and expiry < issue:
        errors["valid_until"] = ["The expiry date can't be before the issue date."]
    document = read_document(files["document"], errors) if files.get("document") else None
    if errors:
        raise ValidationError(errors)
    fields = {"name": name, "issuing_authority": parsing.text(d, "issuing_authority", 150),
              "certificate_number": parsing.text(d, "certificate_number", 80), "category": category or "",
              "issue_date": issue, "valid_until": expiry, "status": cert_status, "notes": parsing.text(d, "notes", 5000)}
    if document:
        fields.update(document_name=document[0], document_type=document[1], document=document[2], document_size=len(document[2]))
    elif current is not None and str(d.get("remove_document") or "").lower() in ("true", "1", "yes"):
        fields.update(document_name="", document_type="", document=None, document_size=None)
    return fields


class CertificationsView(QualityView):
    """GET: every certification. POST (multipart): a new one, its certificate document saved in the same step."""

    def get(self, request):
        today = periods.today()
        return Response([certification_row(c, today) for c in certifications()])

    def post(self, request):
        fields = read_certification(request.data, request.FILES)
        c = Certification.objects.create(created_by=request.user, **fields)
        audit.record(request, "Added certification", c.name)
        return Response(certification_row(c), status=status.HTTP_201_CREATED)


class CertificationDetailView(QualityView):
    def get(self, request, pk):
        return Response(certification_row(get_object_or_404(certifications(), pk=pk)))

    def patch(self, request, pk):
        """Fields not sent keep their value; a new document replaces the old one; remove_document=true removes it."""
        c = get_object_or_404(Certification, pk=pk)
        current = {"name": c.name, "issuing_authority": c.issuing_authority, "certificate_number": c.certificate_number,
                   "category": c.category, "issue_date": c.issue_date.isoformat() if c.issue_date else "",
                   "valid_until": c.valid_until.isoformat() if c.valid_until else "", "status": c.status, "notes": c.notes}
        data = {**current, **{k: request.data.get(k) for k in current if k in request.data},
                "remove_document": request.data.get("remove_document")}
        for k, v in read_certification(data, request.FILES, current=c).items():
            setattr(c, k, v)
        c.save()
        audit.record(request, "Edited certification", c.name)
        return Response(certification_row(c))

    def delete(self, request, pk):
        c = get_object_or_404(certifications(), pk=pk)
        audit.record(request, "Deleted certification", c.name)
        c.delete()  # the document is in the same row, so it goes with it
        return Response(status=status.HTTP_204_NO_CONTENT)


class CertificationDocumentView(QualityView):
    """The stored certificate file, for signed-in users who may open Quality. ?download=1 saves it instead of showing it."""

    def get(self, request, pk):
        c = get_object_or_404(Certification, pk=pk)
        if not c.document_name or c.document is None:
            raise NotFound("No certificate document has been uploaded.")
        response = HttpResponse(bytes(c.document), content_type=c.document_type or "application/octet-stream")
        safe = "".join(ch for ch in c.document_name if ch not in '"\r\n')
        response["Content-Disposition"] = f'{"attachment" if self.param("download") else "inline"}; filename="{safe}"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
