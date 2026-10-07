from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class TransactionQuerySet(models.QuerySet):
    def counted(self):
        """Rows that count in totals: a cancelled transaction (its payment was cancelled) stays visible but counts nowhere."""
        return self.exclude(status=Transaction.Status.CANCELLED)


class Transaction(models.Model):
    """
    One income or expense line in Accounts. Rows linked to a sales payment or a supplier payment are posted
    automatically from that payment (apps/finance/services.py) and change only through it; the others are entered by hand.
    """

    class Type(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    class IncomeCategory(models.TextChoices):
        PRODUCT_SALES = "product_sales", "Product Sales"
        EXPORT_SALES = "export_sales", "Export Sales"
        OTHER_INCOME = "other_income", "Other Income"

    class ExpenseCategory(models.TextChoices):
        RAW_MATERIALS = "raw_materials", "Raw Materials"
        SALARIES = "salaries", "Salaries & Wages"
        UTILITIES = "utilities", "Utilities"
        PACKAGING = "packaging", "Packaging"
        TRANSPORT = "transport", "Transport & Logistics"
        MARKETING = "marketing", "Marketing"
        RENT = "rent", "Rent"
        MAINTENANCE = "maintenance", "Maintenance"
        TAX = "tax", "Taxes & Duties"
        OTHER_EXPENSE = "other_expense", "Other Expenses"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        PENDING = "pending", "Pending"
        CANCELLED = "cancelled", "Cancelled"  # only for posted rows whose payment was cancelled

    # Pending-payment "kind" shown in Accounts → Pending Payments
    KIND_FOR_CATEGORY = {
        "raw_materials": "supplier", "packaging": "supplier", "transport": "supplier",
        "utilities": "utility", "salaries": "salary", "tax": "tax",
    }

    date = models.DateField(db_index=True)
    description = models.CharField(max_length=255)
    type = models.CharField(max_length=7, choices=Type.choices, db_index=True)
    category = models.CharField(max_length=20, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMPLETED, db_index=True)
    party = models.CharField(max_length=150, blank=True, help_text="Customer, supplier or payee")
    due_date = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=60, blank=True)
    # Source payment of a posted row; one-to-one, so a payment can never be posted twice
    sales_payment = models.OneToOneField("sales.SalesPayment", null=True, blank=True, on_delete=models.PROTECT,
                                         related_name="accounts_transaction")
    supplier_payment = models.OneToOneField("purchase.SupplierPayment", null=True, blank=True, on_delete=models.PROTECT,
                                            related_name="accounts_transaction")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TransactionQuerySet.as_manager()

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="transaction_amount_positive"),
            models.CheckConstraint(condition=models.Q(sales_payment__isnull=True) | models.Q(supplier_payment__isnull=True),
                                   name="transaction_one_source"),
        ]

    def __str__(self):
        return f"{self.date} {self.get_type_display()} ₹{self.amount} {self.description}"

    @property
    def is_posted(self):
        return self.sales_payment_id is not None or self.supplier_payment_id is not None

    @classmethod
    def category_label(cls, value):
        for choices in (cls.IncomeCategory, cls.ExpenseCategory):
            if value in choices.values:
                return choices(value).label
        return value

    def clean(self):
        from django.core.exceptions import ValidationError

        allowed = self.IncomeCategory.values if self.type == self.Type.INCOME else self.ExpenseCategory.values
        if self.category not in allowed:
            raise ValidationError({"category": "This category doesn't match the transaction type."})


class Budget(models.Model):
    """Targets for one calendar month (Accounts → Set Budget sets the current month)."""

    month = models.DateField(unique=True, help_text="First day of the month")
    revenue_target = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    expense_limit = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month"]

    def __str__(self):
        return f"Budget {self.month:%b %Y}"
