"""
The attendance window, decided only by the server clock in IST (never by the browser).

The work day is 09:00 AM to 05:30 PM. With the default settings attendance is OPEN from 05:00 PM to 09:20 AM the
next morning and FROZEN from 09:20 AM to 05:00 PM (working hours), repeating every day:

- from 05:00 PM, Check-Out / Logout ends that day's work (a late check-out after midnight still counts for it);
- until 09:20 AM, Check-In starts that morning's work day (09:20 AM is the latest check-in).

So an open window has two dates: the work day a check-out closes (the day the window opened) and the work day a
check-in counts for (the morning the window closes). Every record is filed under its work day.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

IST = ZoneInfo("Asia/Kolkata")
DAY = timedelta(days=1)


def now():
    """Current server time in IST: the only clock attendance uses."""
    return timezone.now().astimezone(IST)


@dataclass(frozen=True)
class Window:
    is_open: bool
    opens_at: datetime            # open: when this window opened; closed: when the next one opens
    closes_at: datetime           # open: when this window closes; closed: when the last one closed
    checkin_date: date | None     # open: the work day a check-in now counts for (the morning the window closes)
    checkout_date: date | None    # open: the work day a check-out now ends (the day the window opened)


def _at(day, tm):
    return datetime.combine(day, tm, tzinfo=IST)


def state(at=None, settings=None):
    from .models import AttendanceSettings

    at = (at or now()).astimezone(IST)
    s = settings or AttendanceSettings.load()
    o, c, d, t = s.open_time, s.close_time, at.date(), at.time().replace(tzinfo=None)

    def open_window(opens, closes):
        return Window(True, opens, closes, closes.date(), opens.date())

    if c <= o:  # overnight window, e.g. 17:00 → 09:20 next morning
        if t >= o:
            return open_window(_at(d, o), _at(d + DAY, c))
        if t < c:
            return open_window(_at(d - DAY, o), _at(d, c))
        return Window(False, _at(d, o), _at(d, c), None, None)
    # same-day window, e.g. 07:00 → 19:00
    if o <= t < c:
        return open_window(_at(d, o), _at(d, c))
    if t < o:
        return Window(False, _at(d, o), _at(d - DAY, c), None, None)
    return Window(False, _at(d + DAY, o), _at(d, c), None, None)


def finished_date(w):
    """The newest work day whose check-in time is over (no check-in by then = absent)."""
    return w.checkin_date - DAY if w.is_open else w.closes_at.date()


def checkout_open_from(w):
    """The oldest work day that can still be checked out now or later today; anything older is final."""
    return w.checkout_date if w.is_open else w.opens_at.date()


def closed_message(w):
    return (f"Attendance is frozen during working hours. Check-in closed at {w.closes_at:%I:%M %p}; "
            f"it opens again at {w.opens_at:%I:%M %p}.")
