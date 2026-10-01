"""Line and document totals shared by purchases, quotations, orders and invoices."""
from decimal import Decimal

ZERO = Decimal("0")
CENT = Decimal("0.01")


def line_amounts(quantity, unit_price, discount_pct, gst_pct):
    """(subtotal, discount, gst, total) for one line: subtotal − discount + GST, each rounded to paise."""
    subtotal = (quantity * unit_price).quantize(CENT)
    discount = (subtotal * discount_pct / 100).quantize(CENT)
    gst = ((subtotal - discount) * gst_pct / 100).quantize(CENT)
    return subtotal, discount, gst, subtotal - discount + gst


def inr(value):
    """₹1,23,456.78 (Indian digit grouping)."""
    value = Decimal(value or 0).quantize(CENT)
    sign = "-" if value < 0 else ""
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}₹{whole}.{frac}"
