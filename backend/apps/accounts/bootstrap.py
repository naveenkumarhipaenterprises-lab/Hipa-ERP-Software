"""
Create the first Super Admin from environment variables, for hosts where you can't run
`manage.py createsuperuser` (such as Vercel).

Set ADMIN_USERNAME, ADMIN_EMAIL and ADMIN_PASSWORD (and optionally ADMIN_NAME) in the host's
environment variables and redeploy. When the server starts, the account is created if no user
with that username exists yet. An existing account is never changed, so the password set here
only applies the first time; change it later from the portal. Remove the variables once you
have logged in.
"""
import logging
import os

logger = logging.getLogger(__name__)


def ensure_admin_from_env():
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    if not (username and password and email):
        return
    if os.environ.get("VERCEL") and os.environ.get("CI"):  # build step: no database work
        return
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            name=os.environ.get("ADMIN_NAME", "").strip() or username,
        )
        logger.warning("Created Super Admin %r from ADMIN_* environment variables.", username)
    except Exception:  # never stop the site from starting because of this
        logger.exception("Could not create the Super Admin from ADMIN_* environment variables.")
