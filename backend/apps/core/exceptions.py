"""
One error format for the whole API:
  { "detail": "message" }                       general errors
  { "field": ["message"], ... }                 validation errors (DRF style)
Stack traces and internals are never returned; they go to the server log.
"""
import logging

from django.db import DatabaseError, OperationalError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("hipa.api")


class InsufficientData(APIException):
    """Analytics / AI requested without enough real records. Never answered with guesses."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Not enough data yet to calculate this."
    default_code = "insufficient_data"


class NotConfigured(APIException):
    """A feature needs set-up (AI provider, messaging channel, backup tool...) that isn't done."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "This feature is not configured on the server yet."
    default_code = "not_configured"


class AnalyticsUnavailable(APIException):
    """An analytics library (pandas / scikit-learn) couldn't be loaded, e.g. Windows blocked one of its files."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = ("The analytics engine is unavailable on the server right now. "
                      "Other features keep working; see the backend log for details.")
    default_code = "analytics_unavailable"


def load_analytics(module, name):
    """
    Imports an analytics function on first use, so a blocked or missing analytics library
    only affects the endpoints that need it instead of stopping the whole server at start-up.
    """
    import importlib

    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, OSError) as exc:
        logger.error("Could not load %s.%s: %s", module, name, exc)
        raise AnalyticsUnavailable() from exc


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        # DRF already produces { detail } / field errors for API, 404, auth and permission errors
        return response

    if isinstance(exc, OperationalError):
        logger.exception("Database unavailable")
        return Response({"detail": "The database is not reachable. Please try again shortly."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if isinstance(exc, DatabaseError):
        logger.exception("Database error")
        return Response({"detail": "A database error occurred. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.exception("Unhandled API error")
    return Response({"detail": "Something went wrong on the server. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
