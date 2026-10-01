"""
Suppliers, raw materials and material movements now live in the Purchase app, and purchase
orders are retired (the business records purchases, not POs). Shipments are rebuilt to point
at the Purchase models.

Destructive: drops supply_chain_shipment, _purchaseorder, _materialmovement, _rawmaterial and
_supplier. Run only after a backup; all five tables were empty when this was written (2026-10-01).
"""
import django.core.validators
import django.db.models.deletion
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_alter_stockmovement_source"),
        ("purchase", "0001_initial"),
        ("supply_chain", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(name="Shipment"),
        migrations.DeleteModel(name="PurchaseOrder"),
        migrations.DeleteModel(name="MaterialMovement"),
        migrations.DeleteModel(name="RawMaterial"),
        migrations.DeleteModel(name="Supplier"),
        migrations.CreateModel(
            name="Shipment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("shipment_number", models.CharField(editable=False, max_length=20, unique=True)),
                ("quantity", models.DecimalField(decimal_places=3, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.001"))])),
                ("unit", models.CharField(choices=[("kg", "Kilogram (kg)"), ("g", "Gram (g)"), ("l", "Litre (l)"), ("ml", "Millilitre (ml)"),
                                                   ("pcs", "Pieces"), ("pkt", "Packet"), ("bag", "Bag"), ("box", "Box"), ("roll", "Roll")],
                                          default="kg", max_length=4)),
                ("destination", models.CharField(max_length=120)),
                ("dispatched_on", models.DateField()),
                ("eta", models.DateField()),
                ("delivered_on", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("in_transit", "In Transit"), ("delayed", "Delayed"), ("delivered", "Delivered")],
                                            db_index=True, default="in_transit", max_length=12)),
                ("quality_passed", models.BooleanField(blank=True, help_text="Inward quality check result, if done", null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("material", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="shipments",
                                               to="purchase.rawmaterial")),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="shipments",
                                              to="inventory.product")),
                ("purchase", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="shipments",
                                               to="purchase.purchase")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="shipments", to="purchase.supplier")),
            ],
            options={
                "ordering": ["-dispatched_on", "-id"],
                "constraints": [models.CheckConstraint(condition=models.Q(models.Q(("material__isnull", False), ("product__isnull", True)),
                                                                          models.Q(("material__isnull", True), ("product__isnull", False)),
                                                                          _connector="OR"), name="shipment_one_item")],
            },
        ),
    ]
