from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from services import notifications

from .models import Product, StockMovement


@transaction.atomic
def move_stock(product, type, quantity_kg, *, source=StockMovement.Source.MANUAL, reference="", note="", user=None):
    """Records a stock movement and updates the product's stock in one transaction (row-locked)."""
    quantity_kg = Decimal(str(quantity_kg))
    if quantity_kg <= 0:
        raise ValidationError({"quantity_kg": ["Quantity must be greater than 0."]})
    locked = Product.objects.select_for_update(of=("self",)).get(pk=product.pk)
    was_low = locked.stock_status != Product.StockStatus.IN_STOCK
    if type == StockMovement.Type.OUT:
        if quantity_kg > locked.stock_kg:
            raise ValidationError({"quantity_kg": [f"Only {locked.stock_kg.normalize():f} kg of {locked.name} is in stock."]})
        locked.stock_kg -= quantity_kg
    else:
        locked.stock_kg += quantity_kg
    locked.save(update_fields=["stock_kg", "updated_at"])
    movement = StockMovement.objects.create(
        product=locked, type=type, quantity_kg=quantity_kg, source=source,
        reference=reference[:50], note=note[:255], created_by=user if user and user.is_authenticated else None,
    )
    product.stock_kg = locked.stock_kg
    if not was_low and locked.stock_status != Product.StockStatus.IN_STOCK:
        transaction.on_commit(lambda: notifications.notify(
            "low_stock",
            f"{locked.name}: {Product.StockStatus(locked.stock_status).label}",
            f"{locked.stock_kg.normalize():f} kg left (reorder level {locked.reorder_level_kg.normalize():f} kg).",
            type="warning" if locked.stock_status == Product.StockStatus.LOW else "error",
            link="/inventory",
        ))
    return movement


# Movements entered by hand; ones from sales / purchase documents are corrected in those documents
UNDOABLE = (StockMovement.Source.MANUAL, StockMovement.Source.OPENING)


@transaction.atomic
def undo_movement(movement):
    """Deletes a hand-entered stock movement and puts the product's stock back (Super Admin corrections)."""
    if movement.source not in UNDOABLE:
        raise ValidationError({"detail": f"This movement came from {movement.get_source_display().lower()} "
                                         f"{movement.reference}; correct it there instead.".replace("  ", " ")})
    locked = Product.objects.select_for_update(of=("self",)).get(pk=movement.product_id)
    if movement.type == StockMovement.Type.IN:
        if movement.quantity_kg > locked.stock_kg:
            raise ValidationError({"detail": f"Only {locked.stock_kg.normalize():f} kg of {locked.name} is left, so this "
                                             f"{movement.quantity_kg.normalize():f} kg stock-in can't be taken back."})
        locked.stock_kg -= movement.quantity_kg
    else:
        locked.stock_kg += movement.quantity_kg
    locked.save(update_fields=["stock_kg", "updated_at"])
    movement.delete()
    return locked
