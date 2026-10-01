from django.conf import settings
from django.db import models

from apps.inventory.models import Product
from apps.production.models import ProductionBatch


class QualityTest(models.Model):
    class Result(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        HOLD = "hold", "Hold"

    # Status shown next to the result
    STATUS_FOR_RESULT = {"pass": "Approved", "fail": "Rejected", "hold": "On Hold"}

    batch = models.ForeignKey(ProductionBatch, on_delete=models.PROTECT, related_name="quality_tests")
    test_date = models.DateField(db_index=True)
    parameters = models.TextField(help_text="What was checked and the readings")
    result = models.CharField(max_length=5, choices=Result.choices, db_index=True)
    notes = models.TextField(blank=True)
    tested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-test_date", "-id"]

    def __str__(self):
        return f"{self.batch} {self.get_result_display()} {self.test_date}"

    @property
    def status(self):
        return self.STATUS_FOR_RESULT[self.result]

    @property
    def testing_hours(self):
        """Hours from batch completion to the test being recorded (None if the batch has no completion time)."""
        done = self.batch.completed_at
        if not done or self.created_at < done:
            return None
        return (self.created_at - done).total_seconds() / 3600


class QualityStandard(models.Model):
    parameter = models.CharField(max_length=120)
    limit = models.CharField(max_length=120, help_text="e.g. ≤ 10% moisture")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.CASCADE, related_name="quality_standards",
                                help_text="Leave empty if it applies to all products")

    class Meta:
        ordering = ["parameter"]
        constraints = [models.UniqueConstraint(fields=["parameter", "product"], name="unique_standard_per_product")]

    def __str__(self):
        return f"{self.parameter}: {self.limit}"


class Certification(models.Model):
    name = models.CharField(max_length=120)
    detail = models.CharField(max_length=255, blank=True, help_text="Licence / certificate number or issuing body")
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["valid_until", "name"]

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
