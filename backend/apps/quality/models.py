from django.conf import settings
from django.db import models

from apps.inventory.models import Product
from apps.purchase.models import GoodsReceipt, RawMaterial


class QualityTest(models.Model):
    """A quality check of one lot of a finished product or raw material, optionally for a goods receipt."""

    class Result(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        HOLD = "hold", "Hold"

    # Status shown next to the result
    STATUS_FOR_RESULT = {"pass": "Approved", "fail": "Rejected", "hold": "On Hold"}
    # Goods-receipt quality status set by a test result
    GRN_STATUS_FOR_RESULT = {"pass": "passed", "fail": "failed", "hold": "on_hold"}

    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT, related_name="quality_tests")
    material = models.ForeignKey(RawMaterial, null=True, blank=True, on_delete=models.PROTECT, related_name="quality_tests")
    goods_receipt = models.ForeignKey(GoodsReceipt, null=True, blank=True, on_delete=models.PROTECT, related_name="quality_tests")
    batch_number = models.CharField("lot / batch number", max_length=40, blank=True, db_index=True)
    test_date = models.DateField(db_index=True)
    parameters = models.TextField(help_text="What was checked and the readings")
    # [{"parameter": "Moisture", "value": "8.5"}] as entered (the value is a decimal number kept as text, so nothing is
    # rounded); `parameters` then holds the same pairs as text for search, exports and reports. Empty for older tests.
    readings = models.JSONField(default=list, blank=True)
    result = models.CharField(max_length=5, choices=Result.choices, db_index=True)
    notes = models.TextField(blank=True)
    tested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-test_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(product__isnull=False, material__isnull=True) |
                                   models.Q(product__isnull=True, material__isnull=False), name="quality_test_one_item"),
        ]

    def __str__(self):
        return f"{self.item} {self.batch_number} {self.get_result_display()} {self.test_date}".replace("  ", " ")

    @property
    def item(self):
        return self.product or self.material

    @property
    def status(self):
        return self.STATUS_FOR_RESULT[self.result]

    @property
    def testing_hours(self):
        """Hours from the goods receipt being recorded to the test being recorded (None without a goods receipt)."""
        received = self.goods_receipt.created_at if self.goods_receipt else None
        if not received or self.created_at < received:
            return None
        return (self.created_at - received).total_seconds() / 3600


class QualityStandard(models.Model):
    parameter = models.CharField(max_length=120)
    limit = models.CharField(max_length=120, help_text="e.g. ≤ 10% moisture")
    # Optional numbers that test readings of this parameter are checked against; `limit` stays the text people read
    min_value = models.DecimalField("lowest acceptable reading", max_digits=12, decimal_places=3, null=True, blank=True)
    max_value = models.DecimalField("highest acceptable reading", max_digits=12, decimal_places=3, null=True, blank=True)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.CASCADE, related_name="quality_standards",
                                help_text="Leave empty if it applies to all products")

    class Meta:
        ordering = ["parameter"]
        constraints = [models.UniqueConstraint(fields=["parameter", "product"], name="unique_standard_per_product")]

    def __str__(self):
        return f"{self.parameter}: {self.limit}"


class Certification(models.Model):
    """
    A food-safety / quality certificate the company holds. The certificate document is kept in this row
    (Vercel's servers have no lasting disk), so the file and its details are always saved together.
    """

    class Category(models.TextChoices):
        FSSAI = "fssai", "FSSAI License"
        ISO = "iso", "ISO Certification"
        HACCP = "haccp", "HACCP"
        GMP = "gmp", "GMP"
        ORGANIC = "organic", "Organic"
        HALAL = "halal", "Halal"
        EXPORT = "export", "Export / Spices Board"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING = "pending", "Pending Verification"
        SUSPENDED = "suspended", "Suspended"

    name = models.CharField(max_length=120)
    detail = models.CharField(max_length=255, blank=True, help_text="Older free text; new entries use the fields below")
    issuing_authority = models.CharField(max_length=150, blank=True)
    certificate_number = models.CharField(max_length=80, blank=True)
    category = models.CharField(max_length=10, choices=Category.choices, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    valid_until = models.DateField("expiry date", null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)
    document = models.BinaryField(null=True, blank=True, editable=False)
    document_name = models.CharField(max_length=150, blank=True)
    document_type = models.CharField(max_length=40, blank=True)
    document_size = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ["valid_until", "name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(issue_date__isnull=True) | models.Q(valid_until__isnull=True) |
                                   models.Q(valid_until__gte=models.F("issue_date")), name="certification_expiry_after_issue"),
        ]

    def __str__(self):
        return self.name


class QualityAudit(models.Model):
    class AuditType(models.TextChoices):
        INTERNAL = "internal", "Internal Audit"
        FSSAI = "fssai", "FSSAI Inspection"
        ISO = "iso", "ISO Audit"
        CUSTOMER = "customer", "Customer Audit"
        SUPPLIER = "supplier", "Supplier Audit"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    audit_type = models.CharField(max_length=10, choices=AuditType.choices)
    date = models.DateField(db_index=True)
    auditor = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)
    findings = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.get_audit_type_display()} on {self.date}"
