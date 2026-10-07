"""
Posts the payments that existed before Accounts was linked to Sales and Purchase (the same rules as
apps/finance/services.py, written out here because migrations use the models as they were at this point).

A hand-entered income row that already records a sales payment (same amount, reference = the invoice number,
not linked yet) becomes that payment's transaction instead of a second one. Safe to run again: payments that
already have a transaction are skipped.
"""
from django.db import migrations

SALES_RECEIVED = "received"
SUPPLIER_MADE = ("paid", "partially_paid")


def reference(number, bank_reference):
    return " / ".join(filter(None, [number, (bank_reference or "").strip()]))[:60]


def post_existing(apps, schema_editor):
    Transaction = apps.get_model("finance", "Transaction")
    SalesPayment = apps.get_model("sales", "SalesPayment")
    SupplierPayment = apps.get_model("purchase", "SupplierPayment")

    for p in SalesPayment.objects.select_related("invoice", "customer").filter(status=SALES_RECEIVED):
        if Transaction.objects.filter(sales_payment=p).exists():
            continue
        t = (Transaction.objects.filter(type="income", amount=p.amount, reference__iexact=p.invoice.invoice_number,
                                        sales_payment__isnull=True, supplier_payment__isnull=True).order_by("id").first()
             or Transaction(created_by_id=p.created_by_id))
        t.sales_payment = p
        t.type, t.category = "income", "export_sales" if p.customer.type == "export" else "product_sales"
        t.description = f"Payment {p.receipt_number} for {p.invoice.invoice_number}"
        t.amount, t.date, t.status, t.due_date = p.amount, p.payment_date, "completed", None
        t.party, t.reference = p.customer.name[:150], reference(p.receipt_number, p.reference)
        t.save()

    for p in SupplierPayment.objects.select_related("supplier", "purchase").filter(status__in=SUPPLIER_MADE):
        if Transaction.objects.filter(supplier_payment=p).exists():
            continue
        Transaction.objects.create(
            supplier_payment=p, created_by_id=p.created_by_id, type="expense", category="raw_materials",
            description=f"Payment {p.payment_number} to {p.supplier.name}"[:200]
                        + (f" for {p.purchase.purchase_number}" if p.purchase_id else ""),
            amount=p.amount, date=p.payment_date, status="completed", party=p.supplier.name[:150],
            reference=reference(p.payment_number, p.transaction_reference))


class Migration(migrations.Migration):
    dependencies = [("finance", "0002_transaction_source_payments")]

    operations = [migrations.RunPython(post_existing, migrations.RunPython.noop)]
