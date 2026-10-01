from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import APIException

from services import ai_client


class Command(BaseCommand):
    help = "Checks the Gemini connection with one tiny real request to GEMINI_MODEL."

    def handle(self, *args, **options):
        try:
            reply = ai_client.check_connection()
        except APIException as exc:
            message = str(exc.detail)
            if "GEMINI_MODEL" in message:
                try:
                    flash = [n for n in ai_client.available_models() if "flash" in n]
                    message += f"\nFlash models listed for this key: {', '.join(flash)}"
                except APIException:
                    pass
            raise CommandError(message)
        self.stdout.write(self.style.SUCCESS(
            f"Gemini connected: model '{settings.GEMINI_MODEL}' answered a test request ({reply[:20]!r})."))
