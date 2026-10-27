"""Apply pending Django migrations on hosts without a shell, such as Vercel."""
import logging
import os

from django.conf import settings
from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor

logger = logging.getLogger(__name__)
LOCK_KEY = 4_810_205_517


def pending(connection):
    executor = MigrationExecutor(connection)
    return executor.migration_plan(executor.loader.graph.leaf_nodes())


def apply_pending_migrations(alias=DEFAULT_DB_ALIAS):
    """Run migrations once per process, serialised across Vercel instances."""
    if not settings.AUTO_MIGRATE or (os.environ.get("VERCEL") and os.environ.get("CI")):
        return
    connection = connections[alias]
    try:
        if not pending(connection):
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [LOCK_KEY])
        try:
            if pending(connection):
                logger.warning("Applying new database migrations at start-up.")
                call_command("migrate", database=alias, interactive=False, verbosity=1)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [LOCK_KEY])
    except Exception:
        # Do not take down the whole site if a parallel instance is already migrating;
        # the full error remains available in the server log for diagnosis.
        logger.exception("Could not apply database migrations at start-up.")
    finally:
        connection.close()
