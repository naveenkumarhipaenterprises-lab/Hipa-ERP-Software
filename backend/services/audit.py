import logging

log = logging.getLogger(__name__)


def record(request, action, target=""):
    """Adds a line to the audit trail (Settings → Audit Logs). Never breaks the request that triggered it."""
    from apps.accounts.views import client_ip
    from apps.system.models import AuditLog

    user = getattr(request, "user", None)
    try:
        AuditLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action=action[:200],
            target=str(target)[:200],
            ip=client_ip(request) if request is not None else None,
        )
    except Exception:
        log.exception("Could not write audit log entry %r", action)
