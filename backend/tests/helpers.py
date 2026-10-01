"""Test helpers. Records created here live only in the throw-away test database."""
from rest_framework.test import APIClient

from apps.accounts.models import User

PASSWORD = "Test-Passw0rd!9"


def make_user(role="admin", username=None, **extra):
    username = username or f"test_{role}"
    return User.objects.create_user(username=username, email=f"{username}@test.invalid", password=PASSWORD,
                                    name=f"TEST {role}", role=role, **extra)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


API = "/api/v1"
