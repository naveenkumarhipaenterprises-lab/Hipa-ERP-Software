"""
Attendance timing, decided only by the server clock in IST (never by the browser).

Two separate rules:
- Check-In window: open from 05:00 PM to 09:20 AM the next morning, closed from 09:20 AM to 05:00 PM, every day.
  A check-in until 09:20 AM starts that morning's work day; a check-in from 05:00 PM counts for the next day.
- Check-Out: allowed at any time for an open record, until 09:20 AM the morning after its work day; after that the
  record is final ("Not checked out"). Nobody is ever checked out automatically.
Office working hours (09:00 AM – 05:30 PM, settings work_start / work_end) are a third, separate rule: they set the
scheduled hours and where approved permission is deducted.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

IST = ZoneInfo("Asia/Kolkata")
DAY = timedelta(days=1)


def now():
    """Current server time in IST: the only clock attendance uses."""
    return timezone.now().astimezone(IST)


@dataclass(frozen=True)
class Window:
    at: datetime                  # the moment this state was worked out for (server time, IST)
    is_open: bool                 # whether Check-In is open
    opens_at: datetime            # open: when this check-in window opened; closed: when the next one opens
    closes_at: datetime           # open: when this check-in window closes; closed: when the last one closed
    checkin_date: date | None     # open: the work day a check-in now counts for (the morning the window closes)
    open_time: time
    close_time: time

    def checkout_deadline(self, work_date):
        """Until when a work day's record can still be checked out: the check-in window closing after it."""
        day = work_date + DAY if self.close_time <= self.open_time else work_date
        return _at(day, self.close_time)

    def can_still_check_out(self, record):
        return record.check_out_at is None and self.at < self.checkout_deadline(record.attendance_date)


def _at(day, tm):
    return datetime.combine(day, tm, tzinfo=IST)


def state(at=None, settings=None):
    from .models import AttendanceSettings

    at = (at or now()).astimezone(IST)
    s = settings or AttendanceSettings.load()
    o, c, d, t = s.open_time, s.close_time, at.date(), at.time().replace(tzinfo=None)

    def make(is_open, opens, closes):
        return Window(at, is_open, opens, closes, closes.date() if is_open else None, o, c)

    if c <= o:  # overnight window, e.g. 17:00 → 09:20 next morning
        if t >= o:
            return make(True, _at(d, o), _at(d + DAY, c))
        if t < c:
            return make(True, _at(d - DAY, o), _at(d, c))
        return make(False, _at(d, o), _at(d, c))
    # same-day window, e.g. 07:00 → 19:00
    if o <= t < c:
        return make(True, _at(d, o), _at(d, c))
    if t < o:
        return make(False, _at(d, o), _at(d - DAY, c))
    return make(False, _at(d + DAY, o), _at(d, c))


def finished_date(w):
    """The newest work day whose check-in time is over (no check-in by then = absent on a working day)."""
    return w.checkin_date - DAY if w.is_open else w.closes_at.date()


def clock(dt_or_time):
    """5:00 PM (no leading zero)."""
    return dt_or_time.strftime("%I:%M %p").lstrip("0")


def closed_message(w):
    return f"Check-In is closed. It opens again at {clock(w.opens_at)}."
