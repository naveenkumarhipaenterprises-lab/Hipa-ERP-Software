"""
Date ranges shared by every overview endpoint.

The frontend sends only a range key; the server turns it into dates in the
company's time zone, together with the previous period of the same length
(used for "vs prev. period" percentages).
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

RANGES = {
    "this_month": "This Month",
    "last_month": "Last Month",
    "last_3_months": "Last 3 Months",
    "this_year": "This Year",
}


@dataclass(frozen=True)
class Period:
    start: date  # inclusive
    end: date  # inclusive
    label: str

    @property
    def days(self):
        return (self.end - self.start).days + 1


def _month_start(d, back=0):
    """First day of the month `back` months before d's month (negative = months ahead)."""
    index = d.year * 12 + (d.month - 1) - back
    return date(index // 12, index % 12 + 1, 1)


def _month_end(d):
    nxt = _month_start(d, -1)
    return nxt - timedelta(days=1)


def today():
    return timezone.localdate()


def start_of(day):
    """Aware datetime at 00:00 local time."""
    return timezone.make_aware(datetime.combine(day, time.min))


def end_of(day):
    """Aware datetime at the last instant of the local day."""
    return timezone.make_aware(datetime.combine(day, time.max))


def moments(start_day, end_day):
    """
    (start, end) datetimes for filtering DateTimeFields by local dates. Use this instead of
    `__date` lookups, which on MySQL need time-zone tables that Windows installs don't have.
    """
    return start_of(start_day), end_of(end_day)


def resolve(range_key, today_=None):
    """Returns (current, previous) periods for a range key. Unknown keys are a validation error."""
    t = today_ or today()
    key = range_key or "this_month"
    if key not in RANGES:
        raise ValidationError({"range": [f"Unknown range '{key}'. Use one of: {', '.join(RANGES)}."]})
    if key == "this_month":
        cur = Period(_month_start(t), t, RANGES[key])
        prev_start = _month_start(t, 1)
        prev = Period(prev_start, min(prev_start + timedelta(days=cur.days - 1), _month_end(prev_start)), "Previous month")
    elif key == "last_month":
        s = _month_start(t, 1)
        cur = Period(s, _month_end(s), RANGES[key])
        ps = _month_start(t, 2)
        prev = Period(ps, _month_end(ps), "Month before")
    elif key == "last_3_months":
        s = _month_start(t, 3)
        cur = Period(s, _month_start(t) - timedelta(days=1), RANGES[key])
        ps = _month_start(t, 6)
        prev = Period(ps, s - timedelta(days=1), "Previous 3 months")
    else:  # this_year
        s = date(t.year, 1, 1)
        cur = Period(s, t, RANGES[key])
        ps = date(t.year - 1, 1, 1)
        prev = Period(ps, ps + timedelta(days=cur.days - 1), "Same period last year")
    return cur, prev


def last_n_months(n, today_=None):
    """Month buckets [(first_day, last_day, 'Jan 2026'), ...], oldest first, ending with the current month."""
    t = today_ or today()
    out = []
    for back in range(n - 1, -1, -1):
        s = _month_start(t, back)
        out.append((s, min(_month_end(s), t), s.strftime("%b %Y")))
    return out


def parse_choice(value, allowed, name, default):
    value = value or default
    if value not in allowed:
        raise ValidationError({name: [f"Must be one of: {', '.join(str(a) for a in allowed)}."]})
    return value
