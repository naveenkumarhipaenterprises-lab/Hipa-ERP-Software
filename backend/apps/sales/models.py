"""
Sales documents. The flow is Customer → Quotation → (accepted) → Sales Order → Sales Invoice → Payment.
A quotation is never an invoice: converting it creates a new order or invoice with its own number,
copying the customer and line items.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.money import ZERO, line_amounts
from apps.core.numbering import save_with_number
from apps.core.periods import today
from apps.customers.models import Customer
from apps.inventory.models import Product

PCT = [MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))]


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = "bank_transfer", "Bank Transfer"
    UPI = "upi", "UPI"
    CHEQUE = "cheque", "Cheque"
    CASH = "cash", "Cash"
    CARD = "card", "Card"
    OTHER = "other", "Other"


class LineAmounts(models.Model):
    """One product line: subtotal − discount + GST = total. `amount` is the taxable value (net sales, excluding GST)."""

    quantity_kg = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(ZERO)])
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO, validators=PCT)
    gst_pct = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO, validators=PCT)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False)
    gst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.subtotal, self.discount_amount, self.gst_amount, self.total = line_amounts(
            self.quantity_kg, self.unit_price, self.discount_pct, self.gst_pct)
        self.amount = self.subtotal - self.discount_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product} × {self.quantity_kg} kg"


class DocumentTotals(models.Model):
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    gst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)

    class Meta:
        abstract = True

    TOTAL_FIELD = "grand_total"

    def recalculate_total(self):
        lines = list(self.items.all())
        self.subtotal = sum((i.subtotal for i in lines), ZERO)
        self.discount_amount = sum((i.discount_amount for i in lines), ZERO)
        self.gst_amount = sum((i.gst_amount for i in lines), ZERO)
        setattr(self, self.TOTAL_FIELD, sum((i.total for i in lines), ZERO))
        self.save(update_fields=["subtotal", "discount_amount", "gst_amount", self.TOTAL_FIELD, "updated_at"])


class CustomerDetails(models.Model):
    """Customer details as printed on the document (copied from the customer, editable per document)."""

    customer_name = models.CharField(max_length=150)
    company_name = models.CharField(max_length=200, blank=True)
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    gstin = models.CharField("GSTIN", max_length=15, blank=True)

    class Meta:
        abstract = True

    PARTY_FIELDS = ("customer_name", "company_name", "billing_address", "shipping_address", "phone", "email", "gstin")


# --- Quotations -------------------------------------------------------------------------------

class SalesQuotation(CustomerDetails, DocumentTotals):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        CONVERTED = "converted", "Converted"

    EDITABLE = (Status.DRAFT, Status.SENT)
    CONVERTIBLE = (Status.DRAFT, Status.SENT, Status.ACCEPTED)
    # Status changes a user may make by hand (conversion and expiry are done by the system)
    TRANSITIONS = {
        Status.DRAFT: (Status.SENT, Status.ACCEPTED, Status.REJECTED),
        Status.SENT: (Status.DRAFT, Status.ACCEPTED, Status.REJECTED),
        Status.ACCEPTED: (Status.REJECTED,),
        Status.REJECTED: (Status.DRAFT,),
        Status.EXPIRED: (Status.DRAFT,),
        Status.CONVERTED: (),
    }

    quotation_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.PROTECT, related_name="quotations")
    quotation_date = models.DateField(db_index=True)
    valid_until = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    payment_terms = models.CharField(max_length=255, blank=True)
    delivery_terms = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    terms_conditions = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-quotation_date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(valid_until__gte=models.F("quotation_date")),
                                              name="quotation_valid_after_date")]

    def __str__(self):
        return self.quotation_number or f"Quotation {self.pk}"

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            return save_with_number(self, "quotation_number", "QT", self.quotation_date, super().save, args, kwargs)
        super().save(*args, **kwargs)


class SalesQuotationItem(LineAmounts):
    quotation = models.ForeignKey(SalesQuotation, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="quotation_items")

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["quotation", "product"], name="unique_product_per_quotation")]


class QuotationStatusChange(models.Model):
    """History of a quotation's status: who changed it, when, and why."""

    quotation = models.ForeignKey(SalesQuotation, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=10, blank=True)
    to_status = models.CharField(max_length=10)
    note = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at", "id"]

    def __str__(self):
        return f"{self.quotation}: {self.from_status or '—'} → {self.to_status}"


# --- Orders -----------------------------------------------------------------------------------

class SalesOrder(DocumentTotals):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        IN_TRANSIT = "in_transit", "In Transit"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    CANCELLABLE = (Status.PENDING, Status.PROCESSING)
    TOTAL_FIELD = "total_amount"

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    quotation = models.OneToOneField(SalesQuotation, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales_order")
    order_date = models.DateField(db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-order_date", "-id"]

    def __str__(self):
        return self.order_number or f"Order {self.pk}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            return save_with_number(self, "order_number", "SO", self.order_date, super().save, args, kwargs)
        super().save(*args, **kwargs)


class SalesOrderItem(LineAmounts):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_kg__gt=0), name="order_item_quantity_positive"),
            models.UniqueConstraint(fields=["order", "product"], name="unique_product_per_order"),
        ]


# --- Invoices ---------------------------------------------------------------------------------

class SalesInvoice(CustomerDetails, DocumentTotals):
    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"

    invoice_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    # One active (not cancelled) invoice per order / quotation, enforced by the services
    sales_order = models.ForeignKey(SalesOrder, null=True, blank=True, on_delete=models.PROTECT, related_name="invoices")
    quotation = models.ForeignKey(SalesQuotation, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    invoice_date = models.DateField(db_index=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ISSUED, db_index=True)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    # Kept up to date by the payment and return services
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    credited_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    # True when this invoice itself took the goods out of stock (no sales order)
    stock_moved = models.BooleanField(default=False, editable=False)
    payment_terms = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    terms_conditions = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(due_date__isnull=True) | models.Q(due_date__gte=models.F("invoice_date")),
                                              name="invoice_due_after_date")]

    def __str__(self):
        return self.invoice_number or f"Invoice {self.pk}"

    @property
    def payable(self):
        return max(self.grand_total - self.credited_amount, ZERO)

    @property
    def balance(self):
        return max(self.payable - self.amount_paid, ZERO)

    @property
    def payment_status(self):
        if self.status == self.Status.CANCELLED:
            return None
        if self.amount_paid >= self.payable:
            return self.PaymentStatus.PAID
        if self.due_date and self.due_date < today():
            return self.PaymentStatus.OVERDUE
        if self.amount_paid > 0:
            return self.PaymentStatus.PARTIALLY_PAID
        return self.PaymentStatus.UNPAID

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            return save_with_number(self, "invoice_number", "INV", self.invoice_date, super().save, args, kwargs)
        super().save(*args, **kwargs)


class SalesInvoiceItem(LineAmounts):
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="invoice_items")

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["invoice", "product"], name="unique_product_per_invoice")]


# --- Payments and returns ---------------------------------------------------------------------

class SalesPayment(models.Model):
    """Money received from a customer against an invoice."""

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    receipt_number = models.CharField(max_length=20, unique=True, editable=False)
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.PROTECT, related_name="payments")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    payment_date = models.DateField(db_index=True)
    payment_method = models.CharField(max_length=13, choices=PaymentMethod.choices)
    reference = models.CharField("transaction reference", max_length=80, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="sales_payment_positive")]

    def __str__(self):
        return self.receipt_number or f"Receipt {self.pk}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            return save_with_number(self, "receipt_number", "RCP", self.payment_date, super().save, args, kwargs)
        super().save(*args, **kwargs)


class SalesReturn(models.Model):
    """Goods a customer sends back against an invoice. Completed returns are credited against the invoice."""

    class Reason(models.TextChoices):
        DAMAGED = "damaged", "Damaged"
        QUALITY = "quality", "Quality issue"
        WRONG_ITEM = "wrong_item", "Wrong item"
        EXCESS = "excess", "Excess quantity"
        EXPIRED = "expired", "Expired"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    return_number = models.CharField(max_length=20, unique=True, editable=False)
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.PROTECT, related_name="returns")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="returns")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sales_returns")
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    return_date = models.DateField(db_index=True)
    reason = models.CharField(max_length=10, choices=Reason.choices)
    amount = models.DecimalField("credit amount", max_digits=14, decimal_places=2, validators=[MinValueValidator(ZERO)])
    restock = models.BooleanField(default=True, help_text="Put the returned goods back into sellable stock")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    remarks = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-return_date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(quantity_kg__gt=0), name="sales_return_quantity_positive")]

    def __str__(self):
        return self.return_number or f"Sales return {self.pk}"

    def save(self, *args, **kwargs):
        if not self.return_number:
            return save_with_number(self, "return_number", "SRT", self.return_date, super().save, args, kwargs)
        super().save(*args, **kwargs)
