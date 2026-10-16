"""
Stops the same form from recording money twice (a double click, or a retry after a slow connection).

A payment form sends a one-time `request_key` (new each time the form opens). The first request with a key claims it
for 10 minutes in the shared cache (the database cache every server process sees); a second request with the same key
is refused. If saving fails (e.g. a wrong amount), the key is released so the corrected form can be sent again.
Requests without a key (older screens, scripts) work as before.
"""
from contextlib import contextmanager

from django.core.cache import cache
from rest_framework import status
from rest_framework.exceptions import APIException

KEEP_SECONDS = 600


class AlreadyRecorded(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This payment was already recorded (the form was sent twice). Refresh the list to see it."
    default_code = "already_recorded"


@contextmanager
def only_once(request, scope):
    key = str(request.data.get("request_key") or "").strip()[:100]
    if not key:
        yield
        return
    name = f"once:{scope}:{request.user.pk}:{key}"
    if not cache.add(name, 1, KEEP_SECONDS):
        raise AlreadyRecorded()
    try:
        yield
    except BaseException:
        cache.delete(name)  # not saved: the same form may be sent again
        raise
