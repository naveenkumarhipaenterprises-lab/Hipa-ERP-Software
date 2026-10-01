import uuid


def save_with_number(instance, field, prefix, date_value, save, args, kwargs):
    """
    First save of a row that shows a readable number (SO-2026-00012): insert with a
    temporary unique value, then set the number from the new id. Ids never repeat,
    so numbers never collide, even with parallel requests.
    """
    setattr(instance, field, f"TMP{uuid.uuid4().hex[:16]}")
    save(*args, **kwargs)
    setattr(instance, field, f"{prefix}-{date_value:%Y}-{instance.pk:05d}")
    kwargs.pop("force_insert", None)
    save(update_fields=[field])
