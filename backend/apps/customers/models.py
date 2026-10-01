from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(r"^[0-9+\-() ]{6,20}$", "Enter a valid phone number.")


class Customer(models.Model):
    class Type(models.TextChoices):
        DISTRIBUTOR = "distributor", "Distributor"
        WHOLESALER = "wholesaler", "Wholesaler"
        RETAILER = "retailer", "Retailer"
        HORECA = "horeca", "Hotel / Restaurant"
        EXPORT = "export", "Export"
        DIRECT = "direct", "Direct Consumer"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=150)
    type = models.CharField(max_length=20, choices=Type.choices, db_index=True)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=80, db_index=True)
    address = models.TextField("billing address", blank=True)
    shipping_address = models.TextField(blank=True, help_text="Leave empty when it is the same as the billing address")
    gstin = models.CharField("GSTIN", max_length=15, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["name", "city"], name="unique_customer_name_city")]

    def __str__(self):
        return f"{self.name} ({self.city})"


class CustomerOffer(models.Model):
    """A promotional message sent to a customer segment (Customers → Send Offers)."""

    segment = models.CharField(max_length=20)  # "all" or a Customer.Type value
    channel = models.CharField(max_length=20)
    message = models.TextField()
    recipients = models.PositiveIntegerField(default=0)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Offer to {self.segment} via {self.channel} ({self.recipients})"
