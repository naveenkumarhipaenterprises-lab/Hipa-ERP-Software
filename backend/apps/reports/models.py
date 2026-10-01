from django.conf import settings
from django.db import models


class Report(models.Model):
    class Type(models.TextChoices):
        SALES = "sales", "Sales Report"
        INVENTORY = "inventory", "Inventory Report"
        PRODUCTION = "production", "Production Report"
        MARKETING = "marketing", "Marketing Report"
        CUSTOMERS = "customers", "Customer Report"
        SUPPLY_CHAIN = "supply_chain", "Supply Chain Report"
        QUALITY = "quality", "Quality Report"
        FINANCE = "finance", "Finance Report"

    class Format(models.TextChoices):
        PDF = "pdf", "PDF"
        XLSX = "xlsx", "Excel"
        CSV = "csv", "CSV"

    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    name = models.CharField(max_length=150)
    type = models.CharField(max_length=15, choices=Type.choices, db_index=True)
    range = models.CharField(max_length=20)
    range_label = models.CharField(max_length=60)
    format = models.CharField(max_length=4, choices=Format.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PROCESSING)
    file = models.FileField(upload_to="reports/%Y/%m/", blank=True)
    error = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="reports")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.name} ({self.format})"
