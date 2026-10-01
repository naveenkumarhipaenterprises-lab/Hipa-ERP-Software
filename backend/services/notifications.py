"""
In-app notifications. Each notification kind has a key in CATALOGUE; admins switch kinds
on or off in Settings → Notifications. Notifications go to every active user whose role
can open the related module.
"""
import logging

from django.contrib.auth import get_user_model

from apps.core.roles import MODULE_READ

log = logging.getLogger(__name__)

# key -> (title shown in Settings, description, module whose users receive it)
CATALOGUE = {
    "low_stock": ("Low stock alerts", "When a product falls to its reorder level", "inventory"),
    "new_orders": ("New sales orders", "When a sales order is created or cancelled", "sales"),
    "quotation_updates": ("Quotation updates", "When a quotation is accepted, rejected or converted", "sales"),
    "quotation_expiry": ("Quotation expiry", "When a quotation passes its valid-until date without a decision", "sales"),
    "customer_payments": ("Customer payments", "When a payment is received against an invoice", "sales"),
    "material_low_stock": ("Raw material reorder alerts", "When a raw material falls to its reorder level", "purchase"),
    "purchase_price_increase": ("Purchase price increases", "When an item is bought at a higher price than last time", "purchase"),
    "goods_receipt_issues": ("Goods receipt issues", "When received goods are damaged, rejected or fail inspection", "purchase"),
    "purchase_returns": ("Purchase returns", "When goods are returned to a supplier", "purchase"),
    "supplier_payment_due": ("Supplier payments due", "When a supplier payment is scheduled, and again when it falls due", "purchase"),
    "supplier_delays": ("Supplier delays", "When a purchase is not received by its expected date", "purchase"),
    "purchase_recommendations": ("Purchase recommendations", "When the daily analysis finds items that need buying soon", "purchase"),
    "invoice_overdue": ("Overdue invoices", "When a sales invoice passes its due date unpaid", "sales"),
    "quality_failures":("Quality test failures", "When a quality test fails or is put on hold", "quality"),
    "shipment_delays": ("Shipment delays", "When a supplier shipment is marked delayed", "supply_chain"),
    "payment_due": ("Pending payments", "When a new pending payment is recorded", "finance"),
    "report_ready": ("Reports ready", "When a report you generated is ready", "reports"),
}


def is_enabled(key):
    from apps.system.models import NotificationPreference

    pref = NotificationPreference.objects.filter(key=key).first()
    return pref.enabled if pref else True


def preferences():
    from apps.system.models import NotificationPreference

    saved = dict(NotificationPreference.objects.values_list("key", "enabled"))
    return [
        {"key": key, "title": title, "description": description, "enabled": saved.get(key, True)}
        for key, (title, description, _module) in CATALOGUE.items()
    ]


def notify(key, title, message="", type="info", link="", users=None):
    """Creates one notification per recipient. `users` overrides the module-based recipients."""
    from apps.system.models import Notification

    if key not in CATALOGUE or not is_enabled(key):
        return 0
    try:
        if users is None:
            roles = MODULE_READ.get(CATALOGUE[key][2], [])
            users = [u for u in get_user_model().objects.filter(is_active=True) if u.effective_role in roles]
        Notification.objects.bulk_create(
            [Notification(user=u, key=key, title=title[:200], message=message, type=type, link=link[:200]) for u in users]
        )
        return len(users)
    except Exception:
        log.exception("Could not create notification %s", key)
        return 0
