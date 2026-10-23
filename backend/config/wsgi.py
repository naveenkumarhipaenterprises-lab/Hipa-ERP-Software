"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# Hosts without a shell (Vercel): new migrations first (apps/core/automigrate.py), then the first Super Admin
# (apps/accounts/bootstrap.py)
from apps.accounts.bootstrap import ensure_admin_from_env  # noqa: E402
from apps.core.automigrate import apply_pending_migrations  # noqa: E402

apply_pending_migrations()
ensure_admin_from_env()
