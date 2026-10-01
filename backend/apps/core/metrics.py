"""Small helpers for KPI payloads built from real aggregates."""
from decimal import Decimal


def num(value):
    """Decimal/None -> JSON-friendly number (floats for money/kg, ints stay ints)."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(round(value, 2))
    return value


def pct_change(current, previous):
    """% change vs the previous period, or None when there is nothing to compare with."""
    if current is None or previous in (None, 0):
        return None
    return round((float(current) - float(previous)) / float(previous) * 100, 1)


def kpi(current, previous=None, compare=True):
    """{ value, change } — change only when the previous period had a value."""
    data = {"value": num(current)}
    if compare:
        change = pct_change(current, previous)
        if change is not None:
            data["change"] = change
    return data


def choices(text_choices):
    """TextChoices -> [{ value, label }] for the frontend's option lists."""
    return [{"value": value, "label": label} for value, label in text_choices.choices]


def label_choices(text_choices):
    """
    For statuses that rows show as text ("Active"): option value = label, so an edit form
    pre-filled from a row matches an option. resolve_choice() accepts either form.
    """
    return [{"value": label, "label": label} for _value, label in text_choices.choices]


def resolve_choice(text_choices, raw, field):
    """Accepts a choice's value or label (any case) and returns the stored value."""
    from rest_framework.exceptions import ValidationError

    if raw in (None, ""):
        return None
    key = str(raw).strip().lower()
    for value, label in text_choices.choices:
        if key in (str(value).lower(), str(label).lower()):
            return value
    allowed = ", ".join(label for _v, label in text_choices.choices)
    raise ValidationError({field: [f"'{raw}' is not valid. Use one of: {allowed}."]})


def ratio_pct(part, whole):
    if not whole:
        return None
    return round(float(part) / float(whole) * 100, 1)
