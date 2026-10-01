"""
Purchase: suppliers, raw materials, purchase transactions, goods receipts (GRN), purchase
returns and supplier payments. There are deliberately no purchase orders and no purchase
invoices: a purchase transaction is recorded once, received through GRNs and paid through
supplier payments.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from apps.core.money import line_amounts
from apps.core.numbering import save_with_number
from apps.core.periods import today
from apps.customers.models import phone_validator
from apps.inventory.models import Product

ZERO = Decimal("0")
CENT = Decimal("0.01")
gstin_validator = RegexValidator(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$", "Enter a valid 15-character GSTIN.")


class Unit(models.TextChoices):
    KG = "kg", "Kilogram (kg)"
    G = "g", "Gram (g)"
    L = "l", "Litre (l)"
    ML = "ml", "Millilitre (ml)"
    PCS = "pcs", "Pieces"
    PKT = "pkt", "Packet"
    BAG = "bag", "Bag"
    BOX = "box", "Box"
    ROLL = "roll", "Roll"


class Supplier(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    supplier_code = models.CharField("supplier ID", max_length=20, unique=True, editable=False)
    name = models.CharField("supplier name", max_length=150, unique=True)
    company_name = models.CharField(max_length=200, blank=True)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=80, db_index=True)
    state = models.CharField(max_length=80, blank=True)
    gstin = models.CharField("GSTIN", max_length=15, blank=True, validators=[gstin_validator])
    payment_terms = models.CharField(max_length=120, blank=True, help_text="e.g. Net 30 days")
    credit_days = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(365)],
                                                   help_text="Days after purchase that payment is due")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    def save(self, *args, **kwargs):
        if not self.supplier_code:
            return save_with_number(self, "supplier_code", "SUP", today(), super().save, args, kwargs)
        super().save(*args, **kwargs)


class RawMaterial(models.Model):
    """Raw spices and packing material. Current stock is the running total of MaterialMovements."""

    class Category(models.TextChoices):
        WHOLE_SPICE = "whole_spice", "Whole Spices"
        SEED = "seed", "Seeds"
        HERB = "herb", "Dried Herbs & Leaves"
        GROUND = "ground", "Ground / Powder"
        PACKAGING = "packaging", "Packing Material"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    material_code = models.CharField("material ID", max_length=20, unique=True, editable=False)
    name = models.CharField("material name", max_length=120, unique=True)
    category = models.CharField(max_length=12, choices=Category.choices, db_index=True)
    unit = models.CharField(max_length=4, choices=Unit.choices, default=Unit.KG)
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, editable=False)
    minimum_stock = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, validators=[MinValueValidator(ZERO)])
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, validators=[MinValueValidator(ZERO)])
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name="materials",
                                 help_text="Usual supplier")
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(ZERO)],
                                         help_text="Standard price per unit")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(current_stock__gte=0), name="raw_material_stock_not_negative"),
            models.CheckConstraint(condition=models.Q(reorder_level__gte=models.F("minimum_stock")), name="material_reorder_at_or_above_min"),
        ]

    def __str__(self):
        return self.name

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def stock_status(self):
        if self.current_stock <= 0:
            return "Out of Stock"
        if self.current_stock <= self.minimum_stock:
            return "Critical"
        if self.current_stock <= self.reorder_level:
            return "Reorder"
        return "In Stock"

    def save(self, *args, **kwargs):
        if not self.material_code:
            return save_with_number(self, "material_code", "RM", today(), super().save, args, kwargs)
        super().save(*args, **kwargs)


class MaterialMovement(models.Model):
    class Type(models.TextChoices):
        IN = "in", "Stock In"
        OUT = "out", "Stock Out"

    class Source(models.TextChoices):
        OPENING = "opening", "Opening stock"
        GOODS_RECEIPT = "goods_receipt", "Goods receipt"
        PURCHASE_RETURN = "purchase_return", "Purchase return"
        RETURN_CANCEL = "return_cancel", "Cancelled return"
        USAGE = "usage", "Used"
        ADJUSTMENT = "adjustment", "Adjustment"

    material = models.ForeignKey(RawMaterial, on_delete=models.PROTECT, related_name="movements")
    type = models.CharField(max_length=3, choices=Type.choices)
    source = models.CharField(max_length=15, choices=Source.choices, default=Source.ADJUSTMENT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    date = models.DateField(db_index=True)
    reference = models.CharField(max_length=50, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0), name="raw_material_movement_positive")]

    def __str__(self):
        return f"{self.get_type_display()} {self.quantity} {self.material.unit} {self.material}"


class Purchase(models.Model):
    """One purchase of a raw material or a finished product from a supplier."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIALLY_RECEIVED = "partially_received", "Partially Received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"

    OPEN = (Status.PENDING, Status.PARTIALLY_RECEIVED)

    purchase_number = models.CharField("purchase ID", max_length=20, unique=True, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    material = models.ForeignKey(RawMaterial, null=True, blank=True, on_delete=models.PROTECT, related_name="purchases")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT, related_name="purchases")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    unit = models.CharField(max_length=4, choices=Unit.choices)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(ZERO)])
    discount_pct = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO,
                                       validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))])
    gst_pct = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO,
                                  validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))])
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, editable=False)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False)
    gst_amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False)
    purchase_date = models.DateField(db_index=True)
    expected_receipt_date = models.DateField(null=True, blank=True)
    payment_due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=18, choices=Status.choices, default=Status.PENDING, db_index=True)
    # Kept up to date by the goods-receipt, return and payment services
    received_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, editable=False)
    returned_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, editable=False)
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-purchase_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(material__isnull=False, product__isnull=True) |
                                   models.Q(material__isnull=True, product__isnull=False), name="purchase_one_item"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="purchase_quantity_positive"),
            models.CheckConstraint(condition=models.Q(expected_receipt_date__isnull=True) |
                                   models.Q(expected_receipt_date__gte=models.F("purchase_date")), name="purchase_receipt_after_date"),
        ]

    def __str__(self):
        return self.purchase_number or f"Purchase {self.pk}"

    @property
    def item(self):
        return self.material or self.product

    @property
    def item_name(self):
        return self.item.name if self.item else ""

    @property
    def item_type(self):
        return "material" if self.material_id else "product"

    @property
    def payable(self):
        return max(self.total_amount - self.returned_amount, ZERO)

    @property
    def balance(self):
        return max(self.payable - self.paid_amount, ZERO)

    @property
    def payment_status(self):
        if self.status == self.Status.CANCELLED:
            return None
        if self.paid_amount >= self.payable:
            return self.PaymentStatus.PAID
        if self.payment_due_date and self.payment_due_date < today():
            return self.PaymentStatus.OVERDUE
        if self.paid_amount > 0:
            return self.PaymentStatus.PARTIALLY_PAID
        return self.PaymentStatus.PENDING

    def calculate(self):
        self.subtotal, self.discount_amount, self.gst_amount, self.total_amount = line_amounts(
            self.quantity, self.unit_price, self.discount_pct, self.gst_pct)

    def save(self, *args, **kwargs):
        self.calculate()
        if not self.purchase_number:
            return save_with_number(self, "purchase_number", "PUR", self.purchase_date, super().save, args, kwargs)
        super().save(*args, **kwargs)


class GoodsReceipt(models.Model):
    """Goods received against a purchase. Only the accepted quantity goes into stock."""

    class QualityStatus(models.TextChoices):
        PENDING = "pending", "Pending Inspection"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        ON_HOLD = "on_hold", "On Hold"

    grn_number = models.CharField("GRN number", max_length=20, unique=True, editable=False)
    purchase = models.ForeignKey(Purchase, on_delete=models.PROTECT, related_name="goods_receipts")
    received_date = models.DateField(db_index=True)
    received_quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    damaged_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, validators=[MinValueValidator(ZERO)])
    accepted_quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(ZERO)])
    quality_status = models.CharField(max_length=8, choices=QualityStatus.choices, default=QualityStatus.PENDING, db_index=True)
    remarks = models.CharField(max_length=500, blank=True)
    stock_recorded = models.BooleanField(default=False, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(received_quantity__gt=0), name="grn_received_positive"),
            models.CheckConstraint(condition=models.Q(damaged_quantity__lte=models.F("received_quantity")), name="grn_damaged_within_received"),
            models.CheckConstraint(condition=models.Q(accepted_quantity__lte=models.F("received_quantity") - models.F("damaged_quantity")),
                                   name="grn_accepted_within_good"),
        ]

    def __str__(self):
        return self.grn_number or f"GRN {self.pk}"

    @property
    def supplier(self):
        return self.purchase.supplier

    @property
    def unit(self):
        return self.purchase.unit

    def save(self, *args, **kwargs):
        if not self.grn_number:
            return save_with_number(self, "grn_number", "GRN", self.received_date, super().save, args, kwargs)
        super().save(*args, **kwargs)


class PurchaseReturn(models.Model):
    """Goods sent back to a supplier. Stock goes out when the return is recorded and back in if it is cancelled."""

    class Reason(models.TextChoices):
        DAMAGED = "damaged", "Damaged"
        QUALITY = "quality", "Failed quality check"
        WRONG_ITEM = "wrong_item", "Wrong item"
        EXCESS = "excess", "Excess quantity"
        EXPIRED = "expired", "Expired"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    return_number = models.CharField("return ID", max_length=20, unique=True, editable=False)
    purchase = models.ForeignKey(Purchase, null=True, blank=True, on_delete=models.PROTECT, related_name="returns")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="returns")
    material = models.ForeignKey(RawMaterial, null=True, blank=True, on_delete=models.PROTECT, related_name="returns")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT, related_name="purchase_returns")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    unit = models.CharField(max_length=4, choices=Unit.choices)
    return_date = models.DateField(db_index=True)
    reason = models.CharField(max_length=10, choices=Reason.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(ZERO)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    remarks = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-return_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(material__isnull=False, product__isnull=True) |
                                   models.Q(material__isnull=True, product__isnull=False), name="purchase_return_one_item"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="purchase_return_quantity_positive"),
        ]

    def __str__(self):
        return self.return_number or f"Return {self.pk}"

    @property
    def item(self):
        return self.material or self.product

    def save(self, *args, **kwargs):
        if not self.return_number:
            return save_with_number(self, "return_number", "PRT", self.return_date, super().save, args, kwargs)
        super().save(*args, **kwargs)


class SupplierPayment(models.Model):
    """
    A payment to a supplier, optionally against one purchase. A scheduled payment is Pending
    (shown as Overdue once its date has passed); a made payment is Paid when it settles the
    purchase and Partially Paid when a balance remains.
    """

    class Method(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        UPI = "upi", "UPI"
        CHEQUE = "cheque", "Cheque"
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"  # shown for pending payments past their date; never stored

    payment_number = models.CharField("payment ID", max_length=20, unique=True, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="payments")
    purchase = models.ForeignKey(Purchase, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(CENT)])
    payment_date = models.DateField(db_index=True)
    payment_method = models.CharField(max_length=13, choices=Method.choices)
    transaction_reference = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDING, db_index=True)
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="supplier_payment_positive")]

    def __str__(self):
        return self.payment_number or f"Payment {self.pk}"

    @property
    def is_made(self):
        return self.status in (self.Status.PAID, self.Status.PARTIALLY_PAID)

    @property
    def display_status(self):
        if self.status == self.Status.PENDING and self.payment_date < today():
            return self.Status.OVERDUE
        return self.status

    def save(self, *args, **kwargs):
        if not self.payment_number:
            return save_with_number(self, "payment_number", "SPY", self.payment_date, super().save, args, kwargs)
        super().save(*args, **kwargs)
