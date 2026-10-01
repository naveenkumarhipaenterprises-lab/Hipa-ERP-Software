"""
Request-body readers for hand-validated endpoints. Each reader records a field error in
`errors` (DRF format) instead of raising, so one response lists every problem at once.
"""
from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from .metrics import resolve_choice


def text(data, name, max_length, *, required=False, errors=None, label=None):
    value = str(data.get(name) or "").strip()
    if required and not value and errors is not None:
        errors[name] = [f"Enter the {label or name.replace('_', ' ')}."]
    return value[:max_length]


def decimal(data, name, errors, *, places=2, minimum=Decimal("0"), maximum=None, positive=False, required=True,
            default=None, message=None):
    """Decimal with at most `places` decimals, >= minimum (> 0 when positive) and <= maximum."""
    raw = data.get(name)
    if raw in (None, ""):
        if required and default is None:
            errors[name] = [message or "This field is required."]
        return default
    try:
        value = Decimal(str(raw))
        if not value.is_finite() or value.as_tuple().exponent < -places:
            raise InvalidOperation
        if (positive and value <= 0) or value < minimum or (maximum is not None and value > maximum):
            raise InvalidOperation
        return value
    except (InvalidOperation, ValueError, TypeError):
        if not message:
            low = "greater than 0" if positive else f"of {minimum:f} or more"
            high = f" and at most {maximum:f}" if maximum is not None else ""
            message = f"Enter a number {low}{high} (up to {places} decimals)."
        errors[name] = [message]
        return None


def date(data, name, errors, *, required=True, label="date"):
    raw = data.get(name)
    if raw in (None, ""):
        if required:
            errors[name] = [f"Enter the {label} (YYYY-MM-DD)."]
        return None
    value = parse_date(str(raw))
    if not value:
        errors[name] = [f"Enter the {label} (YYYY-MM-DD)."]
    return value


def choice(data, name, text_choices, errors, *, required=True, default=None, message=None):
    try:
        value = resolve_choice(text_choices, data.get(name), name)
    except ValidationError as exc:
        errors.update(exc.detail)
        return None
    if not value:
        if default is not None:
            return default
        if required:
            errors[name] = [message or "Choose an option."]
    return value


def record(data, name, queryset, errors, *, required=True, message="Choose an option."):
    """Row from `queryset` whose pk is data[name]."""
    raw = data.get(name)
    if raw in (None, ""):
        if required:
            errors[name] = [message]
        return None
    obj = queryset.filter(pk=raw).first() if str(raw).isdigit() else None
    if not obj:
        errors[name] = [message]
    return obj
