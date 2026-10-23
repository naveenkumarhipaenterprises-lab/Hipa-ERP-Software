"""
Where an employee checked in / out: the GPS position their device sent (latitude, longitude, accuracy in metres),
and the street address the server looks up for it. The address lookup is best effort: when the service is slow or
down, the coordinates are still kept and the map link still works.
"""
import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import ValidationError

log = logging.getLogger(__name__)

REQUIRED = ("Turn on location and allow this app to use it, then try again. "
            "Your location is recorded with every check-in and check-out.")
MAX_ADDRESS = 300
MAX_ACCURACY = 1_000_000  # metres; anything worse is not a position


@dataclass(frozen=True)
class Location:
    latitude: Decimal
    longitude: Decimal
    accuracy: int | None
    address: str = ""


def _number(raw, low, high, name, errors):
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        value = None
    if value is None or not value.is_finite() or not low <= value <= high:
        errors[name] = [f"Send a {name} between {low} and {high}."]
        return None
    return value.quantize(Decimal("0.000001"))


def read(data, required):
    """
    The location in a check-in / check-out request: {"location": {"latitude", "longitude", "accuracy"}}.
    None when none was sent and none is required; a 400 when it is required or isn't a real position.
    """
    raw = data.get("location") if hasattr(data, "get") else None
    if not isinstance(raw, dict) or raw.get("latitude") in (None, "") or raw.get("longitude") in (None, ""):
        if required:
            raise ValidationError({"location": [REQUIRED], "detail": REQUIRED})
        return None
    errors = {}
    lat = _number(raw["latitude"], -90, 90, "latitude", errors)
    lng = _number(raw["longitude"], -180, 180, "longitude", errors)
    accuracy = None
    if raw.get("accuracy") not in (None, ""):
        try:
            accuracy = round(float(raw["accuracy"]))
        except (TypeError, ValueError, OverflowError):
            accuracy = -1
        if not 0 <= accuracy <= MAX_ACCURACY:
            errors["accuracy"] = ["Send the accuracy in metres."]
    if errors:
        raise ValidationError({"location": errors, "detail": "The location from this device isn't valid. Try again."})
    return Location(lat, lng, accuracy)


def with_address(loc):
    """The same location with its street address filled in when the lookup works."""
    if loc is None:
        return None
    return Location(loc.latitude, loc.longitude, loc.accuracy, reverse_geocode(loc.latitude, loc.longitude))


def reverse_geocode(lat, lng):
    """The street address of a position, or "" when it can't be found. Cached per ~10 m square for a month."""
    if settings.ATTENDANCE_GEOCODER != "nominatim":
        return ""
    key = f"attendance:address:{float(lat):.4f},{float(lng):.4f}"
    found = cache.get(key)
    if found is not None:
        return found
    query = urllib.parse.urlencode({"format": "jsonv2", "lat": f"{lat}", "lon": f"{lng}", "zoom": 18,
                                    "addressdetails": 0, "accept-language": "en"})
    agent = "HIPA-MASALA-ERP/1.0 (attendance)" + (f" {settings.ATTENDANCE_GEOCODER_CONTACT}" if settings.ATTENDANCE_GEOCODER_CONTACT else "")
    request = urllib.request.Request(f"{settings.ATTENDANCE_GEOCODER_URL}?{query}", headers={"User-Agent": agent})
    try:
        with urllib.request.urlopen(request, timeout=settings.ATTENDANCE_GEOCODER_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read(200_000).decode("utf-8"))
    except Exception as exc:  # network, HTTP or JSON error: keep the coordinates, try again next time
        log.warning("Attendance address lookup failed: %s", exc)
        return ""
    address = str(body.get("display_name") or "").strip()[:MAX_ADDRESS] if isinstance(body, dict) else ""
    cache.set(key, address, 30 * 24 * 3600)
    return address


def map_url(lat, lng):
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"


def save(record, kind, loc):
    """Puts a location on a record's check-in or check-out (kind "check_in" / "check_out"); returns the field names."""
    if loc is None:
        return []
    values = {"latitude": loc.latitude, "longitude": loc.longitude, "accuracy": loc.accuracy, "address": loc.address}
    for name, value in values.items():
        setattr(record, f"{kind}_{name}", value)
    return [f"{kind}_{name}" for name in values]


def block(record, kind):
    """{"latitude", "longitude", "accuracy", "address", "map_url"} of a record's check-in or check-out, or None."""
    if record is None:
        return None
    lat, lng = getattr(record, f"{kind}_latitude"), getattr(record, f"{kind}_longitude")
    if lat is None or lng is None:
        return None
    return {"latitude": float(lat), "longitude": float(lng), "accuracy": getattr(record, f"{kind}_accuracy"),
            "address": getattr(record, f"{kind}_address") or None, "map_url": map_url(lat, lng)}


def label(record, kind):
    """One line for reports: the address with its coordinates, or just the coordinates."""
    b = block(record, kind)
    if b is None:
        return None
    coords = f"{b['latitude']:.6f}, {b['longitude']:.6f}" + (f" (±{b['accuracy']} m)" if b["accuracy"] is not None else "")
    return f"{b['address']} — {coords}" if b["address"] else coords
