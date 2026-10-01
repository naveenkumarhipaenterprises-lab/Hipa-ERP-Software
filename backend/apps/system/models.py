from django.conf import settings
from django.db import models


class SingletonModel(models.Model):
    """A settings table that always has exactly one row (pk=1), created on first read."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Settings rows can't be deleted.")

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CompanySettings(SingletonModel):
    """General preferences and company details (Settings → General / Company). Empty until an admin fills them in."""

    # General
    company_name = models.CharField(max_length=150, blank=True)
    tagline = models.CharField(max_length=200, blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    date_format = models.CharField(max_length=20, blank=True)
    time_format = models.CharField(max_length=10, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    language = models.CharField(max_length=10, blank=True)
    # Company
    legal_name = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    gstin = models.CharField("GSTIN", max_length=15, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "company settings"

    def __str__(self):
        return self.company_name or "Company settings"


class BillingSettings(SingletonModel):
    """
    Settings → Tax & Billing: GST defaults, quotation and invoice defaults, bank details printed on
    invoices, and purchase defaults. Empty until an admin fills them in; nothing is assumed.
    """

    # Tax / GST
    default_sales_gst_pct = models.DecimalField("default GST % on sales", max_digits=5, decimal_places=2, null=True, blank=True)
    default_purchase_gst_pct = models.DecimalField("default GST % on purchases", max_digits=5, decimal_places=2, null=True, blank=True)
    # Quotations
    quotation_validity_days = models.PositiveSmallIntegerField(null=True, blank=True)
    quotation_payment_terms = models.CharField(max_length=255, blank=True)
    quotation_delivery_terms = models.CharField(max_length=255, blank=True)
    quotation_terms = models.TextField("quotation terms & conditions", blank=True)
    # Invoices
    invoice_due_days = models.PositiveSmallIntegerField(null=True, blank=True)
    invoice_payment_terms = models.CharField(max_length=255, blank=True)
    invoice_terms = models.TextField("invoice terms & conditions", blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)
    bank_account_number = models.CharField(max_length=30, blank=True)
    bank_ifsc = models.CharField("IFSC", max_length=11, blank=True)
    upi_id = models.CharField("UPI ID", max_length=80, blank=True)
    authorised_signatory = models.CharField(max_length=120, blank=True)
    # Purchase / suppliers
    default_supplier_credit_days = models.PositiveSmallIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "billing settings"

    def __str__(self):
        return "Billing settings"


class NotificationPreference(models.Model):
    """On/off switch for each kind of notification the system sends (keys are defined in notifications.CATALOGUE)."""

    key = models.CharField(max_length=40, unique=True)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key}: {'on' if self.enabled else 'off'}"


class Notification(models.Model):
    class Type(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        SUCCESS = "success", "Success"
        ERROR = "error", "Error"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    key = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.INFO)
    link = models.CharField(max_length=200, blank=True)
    read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read"])]

    def __str__(self):
        return f"{self.user}: {self.title}"


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=200)
    target = models.CharField(max_length=200, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.user}: {self.action} {self.target}"


class BackupSettings(SingletonModel):
    RETENTION_CHOICES = [(1, "1 month"), (3, "3 months"), (6, "6 months"), (12, "12 months")]

    automatic = models.BooleanField(default=False)
    retention_months = models.PositiveSmallIntegerField(choices=RETENTION_CHOICES, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "backup settings"

    def __str__(self):
        return "Backup settings"


class BackupRun(models.Model):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    file_name = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    error = models.TextField(blank=True)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Backup {self.started_at:%Y-%m-%d %H:%M} {self.status}"
