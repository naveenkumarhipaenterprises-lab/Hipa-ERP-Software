"""Rate limit for the Django admin sign-in page (/admin/login/), which the API's throttles don't cover."""
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from rest_framework.throttling import ScopedRateThrottle

from .views import client_ip


def throttle_failed_logins(login_view):
    """Blocks an IP after as many failed admin sign-ins as the API login allows (LOGIN_THROTTLE_RATE)."""

    @wraps(login_view)
    def view(request, *args, **kwargs):
        if request.method != "POST":
            return login_view(request, *args, **kwargs)
        limit, period = ScopedRateThrottle().parse_rate(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login"])
        key = f"admin-login-failures:{client_ip(request)}"
        if cache.get(key, 0) >= limit:
            return HttpResponse("Too many failed sign-in attempts. Please wait a minute and try again.",
                                status=429, content_type="text/plain; charset=utf-8")
        response = login_view(request, *args, **kwargs)
        if response.status_code == 200:  # the form was shown again: wrong username or password
            cache.add(key, 0, period)
            try:
                cache.incr(key)
            except ValueError:  # the window ended in between
                cache.set(key, 1, period)
        return response

    return view
