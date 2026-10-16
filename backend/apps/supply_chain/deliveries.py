"""
Customer deliveries: the outbound side of a sales order (inbound supplier shipments are Shipment, kept apart).

One delivery status, used by the Supply Chain dashboard, the Customer Deliveries list and Sales orders alike:

    Delivered   the order is Delivered: someone confirmed the delivery (Confirm Delivery, or Mark Delivered in Sales)
    Delayed     not delivered yet and the expected delivery date has passed (never without an expected date)
    In Transit  dispatched (order In Transit), not overdue
    Pending     Pending / Processing order, not overdue: still being prepared

Cancelled orders are not deliveries and are left out. The four statuses don't overlap, so they add up to the total.
"""
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core import periods
from apps.sales.models import SalesOrder

from .models import CustomerDelivery

St = SalesOrder.Status

PENDING, IN_TRANSIT, DELIVERED, DELAYED = "pending", "in_transit", "delivered", "delayed"
LABELS = {PENDING: "Pending", IN_TRANSIT: "In Transit", DELIVERED: "Delivered", DELAYED: "Delayed"}
STATUS_CHOICES = [{"value": k, "label": v} for k, v in LABELS.items()]
PREPARING = (St.PENDING, St.PROCESSING)


def status_of(order, today=None):
    """Delivery status key of one order (None for a cancelled order)."""
    if order.status == St.CANCELLED:
        return None
    if order.status == St.DELIVERED:
        return DELIVERED
    d = delivery_of(order)
    if d and d.expected_delivery_date and d.expected_delivery_date < (today or periods.today()):
        return DELAYED
    return IN_TRANSIT if order.status == St.IN_TRANSIT else PENDING


def label_of(order, today=None):
    key = status_of(order, today)
    return LABELS[key] if key else order.get_status_display()


def _has_delivery(order):
    try:
        return order.delivery is not None
    except CustomerDelivery.DoesNotExist:
        return False


def delivery_of(order):
    return order.delivery if _has_delivery(order) else None


def status_filters(today=None):
    """The same rules as status_of() as query filters on SalesOrder, for counting and filtering in the database."""
    t = today or periods.today()
    overdue = Q(delivery__expected_delivery_date__lt=t)
    on_time = Q(delivery__isnull=True) | Q(delivery__expected_delivery_date__isnull=True) | Q(delivery__expected_delivery_date__gte=t)
    return {
        DELIVERED: Q(status=St.DELIVERED),
        DELAYED: Q(status__in=(*PREPARING, St.IN_TRANSIT)) & overdue,
        IN_TRANSIT: Q(status=St.IN_TRANSIT) & on_time,
        PENDING: Q(status__in=PREPARING) & on_time,
    }


def eligible_orders():
    """Every sales order that needs delivery tracking: all but cancelled ones."""
    return SalesOrder.objects.exclude(status=St.CANCELLED)


def summary(today=None):
    """{total, pending, in_transit, delivered, delayed} over every eligible order, in one query."""
    f = status_filters(today)
    counts = eligible_orders().aggregate(total=Count("id"), **{k: Count("id", filter=q) for k, q in f.items()})
    return {"total": counts["total"], **{k: counts[k] for k in (PENDING, IN_TRANSIT, DELIVERED, DELAYED)}}


def _record(order):
    d = delivery_of(order)
    return d or CustomerDelivery(order=order)


def check_expected(order, expected, dispatched_on=None, errors=None):
    if expected and expected < order.order_date:
        errors["expected_delivery_date"] = ["The expected delivery date can't be before the order date."]
    elif expected and dispatched_on and expected < dispatched_on:
        errors["expected_delivery_date"] = ["The expected delivery date can't be before the dispatch date."]


def dispatch(order, user, *, dispatched_on=None, carrier=None, tracking_reference=None, expected_delivery_date=None):
    """Pending / Processing order -> In Transit, recording the dispatch. `order` must be locked (select_for_update)."""
    if order.status not in PREPARING:
        raise ValidationError({"detail": f"A {order.get_status_display().lower()} order can't be dispatched."})
    t = periods.today()
    dispatched_on = dispatched_on or t
    errors = {}
    if dispatched_on > t:
        errors["dispatched_on"] = ["The dispatch date can't be in the future."]
    elif dispatched_on < order.order_date:
        errors["dispatched_on"] = ["The dispatch date can't be before the order date."]
    d = _record(order)
    expected = expected_delivery_date or d.expected_delivery_date
    if expected_delivery_date:
        check_expected(order, expected_delivery_date, dispatched_on, errors)
    elif expected and expected < dispatched_on:
        errors["expected_delivery_date"] = [f"The saved expected delivery date ({expected:%d %b %Y}) is before the dispatch date. "
                                            "Enter a new expected delivery date."]
    if errors:
        raise ValidationError(errors)
    d.dispatched_on = dispatched_on
    d.expected_delivery_date = expected
    if carrier is not None:
        d.carrier = carrier
    if tracking_reference is not None:
        d.tracking_reference = tracking_reference
    with transaction.atomic():
        d.save()
        order.status = St.IN_TRANSIT
        order.save(update_fields=["status", "updated_at"])
    return d


def confirm(order, user, *, delivered_on=None, received_by=None, notes=None):
    """In Transit order -> Delivered. This explicit confirmation is the only way an order becomes Delivered."""
    if order.status != St.IN_TRANSIT:
        if order.status in PREPARING:
            raise ValidationError({"detail": "Dispatch the order before confirming its delivery."})
        raise ValidationError({"detail": f"A {order.get_status_display().lower()} order can't be confirmed as delivered."})
    t = periods.today()
    d = _record(order)
    delivered_on = delivered_on or t
    errors = {}
    if delivered_on > t:
        errors["delivered_on"] = ["The delivery date can't be in the future."]
    elif delivered_on < (d.dispatched_on or order.order_date):
        errors["delivered_on"] = ["The delivery date can't be before the dispatch date."]
    if errors:
        raise ValidationError(errors)
    d.delivered_on = delivered_on
    if received_by is not None:
        d.received_by = received_by
    if notes:
        d.notes = notes
    d.confirmed_by = user if user and user.is_authenticated else None
    d.confirmed_at = timezone.now()
    with transaction.atomic():
        d.save()
        order.status = St.DELIVERED
        order.save(update_fields=["status", "updated_at"])
    return d
