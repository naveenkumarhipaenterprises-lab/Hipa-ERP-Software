"""
Accounts posting: sales payments and supplier payments flow into Accounts by themselves.

    Sales payment (received)          -> Income  (Product Sales; Export Sales for export customers)
    Supplier payment (paid / partly)  -> Expense (Raw Materials)
    Payment cancelled                 -> its transaction is marked Cancelled (kept, left out of every total)
    Supplier payment still scheduled  -> nothing yet (posted when it is marked paid)

Each payment has at most one transaction (one-to-one link), and every save of the payment updates that same row,
so nothing is ever posted twice. Amounts are the cash that moved, GST included. Posted rows change only through
their payment: Accounts doesn't let them be edited.
"""
from django.db.models.signals import post_save

from .models import Transaction

T = Transaction


def _reference(number, bank_reference):
    return " / ".join(filter(None, [number, (bank_reference or "").strip()]))[:60]


def _post(link, payment, *, counts, cancelled, fields):
    """Creates or updates the transaction linked to `payment` (link = "sales_payment" | "supplier_payment")."""
    t = T.objects.filter(**{link: payment}).first()
    if t is None:
        if not counts:  # scheduled, or cancelled before it was ever posted: nothing to record
            return None
        t = T(**{link: payment}, created_by=payment.created_by)
    elif not counts and not cancelled:
        return t  # back to scheduled can't happen today; leave the row as it is
    for name, value in fields.items():
        setattr(t, name, value)
    t.status = T.Status.CANCELLED if cancelled else T.Status.COMPLETED
    t.due_date = None
    t.save()
    return t


def post_sales_payment(payment):
    from apps.customers.models import Customer
    from apps.sales.models import SalesPayment

    customer, invoice = payment.customer, payment.invoice
    export = customer.type == Customer.Type.EXPORT
    return _post("sales_payment", payment,
                 counts=payment.status == SalesPayment.Status.RECEIVED,
                 cancelled=payment.status == SalesPayment.Status.CANCELLED,
                 fields={"type": T.Type.INCOME,
                         "category": T.IncomeCategory.EXPORT_SALES if export else T.IncomeCategory.PRODUCT_SALES,
                         "description": f"Payment {payment.receipt_number} for {invoice.invoice_number}",
                         "amount": payment.amount, "date": payment.payment_date, "party": customer.name[:150],
                         "reference": _reference(payment.receipt_number, payment.reference)})


def post_supplier_payment(payment):
    from apps.purchase.models import SupplierPayment

    S = SupplierPayment.Status
    purchase = payment.purchase
    return _post("supplier_payment", payment,
                 counts=payment.status in (S.PAID, S.PARTIALLY_PAID),
                 cancelled=payment.status == S.CANCELLED,
                 fields={"type": T.Type.EXPENSE, "category": T.ExpenseCategory.RAW_MATERIALS,
                         "description": f"Payment {payment.payment_number} to {payment.supplier.name}"[:200]
                                        + (f" for {purchase.purchase_number}" if purchase else ""),
                         "amount": payment.amount, "date": payment.payment_date, "party": payment.supplier.name[:150],
                         "reference": _reference(payment.payment_number, payment.transaction_reference)})


def _on_sales_payment_saved(sender, instance, raw=False, **kwargs):
    if not raw:  # fixtures load rows as they are
        post_sales_payment(instance)


def _on_supplier_payment_saved(sender, instance, raw=False, **kwargs):
    if not raw:
        post_supplier_payment(instance)


def connect():
    """Called from FinanceConfig.ready(): every save of a payment (any screen, admin or command) updates Accounts."""
    post_save.connect(_on_sales_payment_saved, sender="sales.SalesPayment", dispatch_uid="accounts-post-sales-payment")
    post_save.connect(_on_supplier_payment_saved, sender="purchase.SupplierPayment", dispatch_uid="accounts-post-supplier-payment")
