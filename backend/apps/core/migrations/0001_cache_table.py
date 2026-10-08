"""
Creates the shared cache table (settings.CACHES, DatabaseCache "django_cache") in Supabase, so rate-limit
counters and cached results are shared by every server process (Vercel runs several and restarts them).
Row level security is switched on for it afterwards by core.apps.lock_public_tables, like every other table.
"""
from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


def drop_cache_table(apps, schema_editor):
    schema_editor.execute("DROP TABLE IF EXISTS django_cache")


class Migration(migrations.Migration):
    dependencies = []

    operations = [migrations.RunPython(create_cache_table, drop_cache_table)]
