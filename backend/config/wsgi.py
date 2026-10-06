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

# First Super Admin on hosts without a shell (Vercel): see apps/accounts/bootstrap.py
from apps.accounts.bootstrap import ensure_admin_from_env  # noqa: E402

ensure_admin_from_env()
