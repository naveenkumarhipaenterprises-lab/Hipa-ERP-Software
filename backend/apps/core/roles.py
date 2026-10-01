"""
Roles and module access. This mirrors the frontend's NAV_ITEMS (src/utils/constants.js)
and the "who can change data" rules on each screen, and is enforced on the server.
"""
from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Super Admin"
    MANAGEMENT = "management", "Management"
    SALES = "sales", "Sales Team"
    PURCHASE = "purchase", "Purchase Team"
    INVENTORY = "inventory", "Inventory Team"
    MARKETING = "marketing", "Marketing Team"
    FINANCE = "finance", "Finance Team"
    QUALITY = "quality", "Quality Team"
    SUPPLY_CHAIN = "supply_chain", "Supply Chain Team"


ALL = [r.value for r in Role]

# Who may open (read) each module
MODULE_READ = {
    "dashboard": ALL,
    "sales": ["admin", "management", "sales", "marketing", "finance"],
    "inventory": ["admin", "management", "inventory", "purchase", "supply_chain"],
    "purchase": ["admin", "management", "purchase", "inventory", "finance", "supply_chain"],
    "marketing": ["admin", "management", "marketing"],
    "customers": ["admin", "management", "sales", "marketing"],
    "supply_chain": ["admin", "management", "inventory", "quality", "purchase", "supply_chain"],
    "quality": ["admin", "management", "quality", "purchase"],
    "finance": ["admin", "management", "finance"],
    "ai_assistant": ALL,
    "reports": ALL,
    "settings": ["admin", "management"],
}

# Who may create / change records in each module
MODULE_WRITE = {
    "sales": ["admin", "management", "sales"],
    "sales_payments": ["admin", "management", "sales", "finance"],
    "inventory": ["admin", "management", "inventory"],
    "purchase": ["admin", "management", "purchase"],
    "supplier_payments": ["admin", "management", "purchase", "finance"],
    "material_stock": ["admin", "management", "purchase", "inventory"],
    "marketing": ["admin", "management", "marketing"],
    "customers": ["admin", "management", "sales"],
    "customer_offers": ["admin", "management", "marketing"],
    "supply_chain": ["admin", "management", "inventory", "supply_chain"],
    "quality": ["admin", "management", "quality"],
    "finance": ["admin", "management", "finance"],
    "reports": ALL,
    "ai_assistant": ALL,
    "settings": ["admin", "management"],
}


def role_of(user):
    if not user or not user.is_authenticated:
        return None
    # Django superusers created with createsuperuser act as admins
    return "admin" if user.is_superuser else getattr(user, "role", None)


def can_read(user, module):
    return role_of(user) in MODULE_READ.get(module, [])


def can_write(user, module):
    return role_of(user) in MODULE_WRITE.get(module, [])
