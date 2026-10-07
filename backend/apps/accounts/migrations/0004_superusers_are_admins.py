from django.db import migrations


def superusers_are_admins(apps, schema_editor):
    apps.get_model("accounts", "User").objects.filter(is_superuser=True).exclude(role="admin").update(role="admin")


class Migration(migrations.Migration):
    """Superusers act as admins; store that role too (one was created with the default "sales")."""

    dependencies = [("accounts", "0003_user_token_version")]

    operations = [migrations.RunPython(superusers_are_admins, migrations.RunPython.noop)]
