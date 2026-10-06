from django.apps import AppConfig
from django.db.models.signals import post_migrate


def lock_public_tables(using="default", **kwargs):
    """
    Turns on row level security for every table in Supabase's "public" schema. Supabase serves that
    schema through its REST API to anyone holding the anon key; with RLS on and no policies, that API
    returns nothing. Django connects as the table owner, so its own queries are unaffected.
    """
    from django.db import connections

    connection = connections[using]
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity"
        )
        for (table,) in cursor.fetchall():
            cursor.execute(f"ALTER TABLE public.{connection.ops.quote_name(table)} ENABLE ROW LEVEL SECURITY")


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"
    verbose_name = "Core"

    def ready(self):
        post_migrate.connect(lock_public_tables, dispatch_uid="core.lock_public_tables")
