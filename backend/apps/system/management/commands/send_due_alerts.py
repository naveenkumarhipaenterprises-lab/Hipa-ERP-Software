"""
Daily reminders from real records (run by scripts/daily_tasks.py). Each alert is sent once per record:
  - purchases past their expected receipt date and not fully received  -> supplier_delays
  - scheduled supplier payments due within 2 days or overdue            -> supplier_payment_due
  - sales invoices past their due date with a balance                   -> invoice_overdue
"""
from datetime import timedelta

from django.core.management.base import BaseCommand

from apps.core.periods import today
from apps.system.models import Notification
from services import notifications


def once(key, title, message, link, type="warning"):
    """Sends the alert unless one with the same key and title was already sent."""
    if Notification.objects.filter(key=key, title=title).exists():
        return 0
    return 1 if notifications.notify(key, title, message, type=type, link=link) else 0


class Command(BaseCommand):
    help = "Send reminders for late supplier deliveries, supplier payments due and overdue invoices."

    def handle(self, *args, **options):
        from apps.purchase.models import Purchase, SupplierPayment
        from apps.sales.models import SalesInvoice

        t = today()
        sent = 0
        for p in Purchase.objects.select_related("supplier", "material", "product").filter(status__in=Purchase.OPEN,
                                                                                            expected_receipt_date__lt=t):
            sent += once("supplier_delays", f"{p.purchase_number} not received on time",
                         f"{p.item_name} from {p.supplier.name} was expected {p.expected_receipt_date:%d %b %Y}.",
                         "/purchase?tab=purchases")
        for pm in SupplierPayment.objects.select_related("supplier").filter(status=SupplierPayment.Status.PENDING,
                                                                            payment_date__lte=t + timedelta(days=2)):
            sent += once("supplier_payment_due", f"Supplier payment {pm.payment_number} due {pm.payment_date:%d %b %Y}",
                         f"₹{pm.amount:,.2f} to {pm.supplier.name}.", "/purchase?tab=payments",
                         type="error" if pm.payment_date < t else "warning")
        for inv in SalesInvoice.objects.filter(status=SalesInvoice.Status.ISSUED, due_date__lt=t):
            if inv.balance > 0:
                sent += once("invoice_overdue", f"Invoice {inv.invoice_number} is overdue",
                             f"{inv.customer_name}: ₹{inv.balance:,.2f} was due {inv.due_date:%d %b %Y}.", "/sales?tab=invoices",
                             type="error")
        self.stdout.write(f"send_due_alerts: {sent} alert(s) sent")
