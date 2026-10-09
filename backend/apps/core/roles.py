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
    FINANCE = "finance", "Accounts Team"
    QUALITY = "quality", "Quality Team"
    SUPPLY_CHAIN = "supply_chain", "Supply Chain Team"


ALL = [r.value for r in Role]

# Who may open (read) each module. A team role opens only the modules where it does its own work (where it may
# change data, see MODULE_WRITE), plus Attendance. Super Admin and Management see everything.
# Someone working in several areas gets extra roles (Settings -> Users -> Roles), e.g. Purchase + Inventory.
MODULE_READ = {
    "dashboard": ["admin", "management"],
    "sales": ["admin", "management", "sales", "finance"],  # Accounts records customer payments
    "inventory": ["admin", "management", "inventory"],
    "purchase": ["admin", "management", "purchase", "inventory", "finance"],  # Inventory: raw-material stock; Accounts: supplier payments
    "marketing": ["admin", "management", "marketing"],
    "customers": ["admin", "management", "sales", "marketing"],  # Marketing sends customer offers
    "supply_chain": ["admin", "management", "inventory", "supply_chain"],
    "quality": ["admin", "management", "quality"],
    # Every user opens Attendance; each action checks its own per-user permission (apps/attendance/permissions.py)
    "attendance": ALL,
    "ai_assistant": ["admin", "management"],
    "reports": ["admin", "management"],
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
    "attendance": ALL,
    "reports": ["admin", "management"],
    "ai_assistant": ["admin", "management"],
    "settings": ["admin", "management"],
}


def role_of(user):
    if not user or not user.is_authenticated:
        return None
    # Django superusers created with createsuperuser act as admins
    return "admin" if user.is_superuser else getattr(user, "role", None)


def roles_of(user):
    """Every role the user holds: the main role plus any extra roles (Settings -> Users)."""
    if not user or not user.is_authenticated:
        return []
    if user.is_superuser:
        return ["admin"]
    all_roles = getattr(user, "all_roles", None)
    return list(all_roles) if all_roles is not None else [getattr(user, "role", None)]


def has_any_role(user, roles):
    return any(r in roles for r in roles_of(user))


def modules_readable(user):
    return [m for m, roles in MODULE_READ.items() if has_any_role(user, roles)]


def can_read(user, module):
    return has_any_role(user, MODULE_READ.get(module, []))


def can_write(user, module):
    return has_any_role(user, MODULE_WRITE.get(module, []))
