from django.db import migrations, models


class Migration(migrations.Migration):
    """Extra team roles on top of the main role (e.g. Purchase + Inventory)."""

    dependencies = [("accounts", "0005_alter_user_role")]

    operations = [
        migrations.AddField(model_name="user", name="extra_roles", field=models.JSONField(blank=True, default=list)),
    ]
