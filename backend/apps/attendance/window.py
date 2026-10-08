"""
The attendance window, decided only by the server clock in IST (never by the browser).

With the default settings it is OPEN from 05:00 PM to 09:20 AM the next day and CLOSED from 09:20 AM to
05:00 PM, every day: one continuous overnight window, filed under the date it opened.
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
    attendance_date: date | None  # the open window's date (the day it opened); None while closed
    opens_at: datetime            # open: when this window opened; closed: when the next one opens
    closes_at: datetime           # open: when this window closes; closed: when the last one closed
    last_date: date               # date of the most recent window that has opened (the current one while open)


def _at(day, tm):
    return datetime.combine(day, tm, tzinfo=IST)


def state(at=None, settings=None):
    from .models import AttendanceSettings

    at = (at or now()).astimezone(IST)
    s = settings or AttendanceSettings.load()
    o, c, d, t = s.open_time, s.close_time, at.date(), at.time().replace(tzinfo=None)
    if c <= o:  # overnight window, e.g. 17:00 → 09:20 next day
        if t >= o:
            return Window(True, d, _at(d, o), _at(d + DAY, c), d)
        if t < c:
            return Window(True, d - DAY, _at(d - DAY, o), _at(d, c), d - DAY)
        return Window(False, None, _at(d, o), _at(d, c), d - DAY)
    # same-day window, e.g. 09:00 → 18:00
    if o <= t < c:
        return Window(True, d, _at(d, o), _at(d, c), d)
    if t < o:
        return Window(False, None, _at(d, o), _at(d - DAY, c), d - DAY)
    return Window(False, None, _at(d + DAY, o), _at(d, c), d)


def last_finished_date(w):
    """The newest window date whose window has already closed (attendance for it is final)."""
    return w.last_date - DAY if w.is_open else w.last_date


def closed_message(w):
    return f"Attendance is closed. Today's attendance window closed at {w.closes_at:%I:%M %p}; it opens again at {w.opens_at:%I:%M %p}."
