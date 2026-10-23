"""
Apply new database migrations when the server starts, for hosts where you can't run `manage.py migrate`
yourself (such as Vercel, whose build step has no database access). On by default on Vercel; set AUTO_MIGRATE=false
to turn it off, or AUTO_MIGRATE=true to use it elsewhere.

Each server process checks once at start-up (one quick query when nothing is new). When migrations are
waiting, a Postgres advisory lock lets only one process apply them; the others wait, then find nothing left to do.
A failure is logged and never stops the site from starting.
"""
import logging
import os

from django.conf import settings
from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor

logger = logging.getLogger(__name__)

LOCK_KEY = 4_810_205_517  # any fixed number: "HIPA migrations"


def pending(connection):
    executor = MigrationExecutor(connection)
    return executor.migration_plan(executor.loader.graph.leaf_nodes())


def apply_pending_migrations(alias=DEFAULT_DB_ALIAS):
    if not settings.AUTO_MIGRATE:
        return
    if os.environ.get("VERCEL") and os.environ.get("CI"):  # build step: no database work
        return
    connection = connections[alias]
    try:
        if not pending(connection):
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [LOCK_KEY])
        try:
            if pending(connection):  # another process may have applied them while this one waited
                logger.warning("Applying new database migrations at start-up.")
                call_command("migrate", database=alias, interactive=False, verbosity=1)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [LOCK_KEY])
    except Exception:  # never stop the site from starting because of this
        logger.exception("Could not apply the database migrations at start-up. Run `python manage.py migrate`.")
    finally:
        connection.close()
