from rest_framework import serializers

from .models import Customer


class CustomerWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["name", "type", "contact_person", "phone", "email", "city", "address", "status"]
        extra_kwargs = {"status": {"required": False}}

    def validate_name(self, value):
        return value.strip()

    def validate_city(self, value):
        return value.strip()

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", ""))
        city = attrs.get("city", getattr(self.instance, "city", ""))
        qs = Customer.objects.filter(name__iexact=name, city__iexact=city)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"name": [f"A customer named {name} in {city} already exists."]})
        return attrs


def customer_row(c):
    """List row; total_orders / total_purchase / last_order_date come from annotations (cancelled orders excluded)."""
    return {
        "id": c.id,
        "name": c.name,
        "type": c.type,
        "type_label": c.get_type_display(),
        "city": c.city,
        "address": c.address,
        "contact_person": c.contact_person,
        "phone": c.phone,
        "email": c.email,
        "total_orders": getattr(c, "total_orders", 0) or 0,
        "total_purchase": float(getattr(c, "total_purchase", 0) or 0),
        "last_order_date": getattr(c, "last_order_date", None),
        "status": c.get_status_display(),
    }
