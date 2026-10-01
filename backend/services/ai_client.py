"""
Client for the AI engine used by the AI Assistant chat: Google Gemini (google-genai SDK).

The API key lives only in backend/.env (GEMINI_API_KEY) and is used only here, on the server.
Without a key the assistant reports "not connected"; it never produces answers of its own.
"""
import logging

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.core.exceptions import NotConfigured

log = logging.getLogger(__name__)


class AIEngineError(APIException):
    """The AI engine is configured but couldn't answer this time."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "The AI engine could not answer right now. Please try again shortly."
    default_code = "ai_engine_error"


class AIRateLimited(AIEngineError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "The AI engine's free-tier limit was reached. Please wait a minute and try again."
    default_code = "ai_rate_limited"


def is_configured():
    return bool(settings.GEMINI_API_KEY)


def model_name():
    return settings.GEMINI_MODEL if is_configured() else None


def _client():
    """
    A new SDK client. Always use it as `with _client() as client:`: the SDK closes its HTTP
    connection when the Client object is garbage-collected, so a client that isn't kept in a
    variable (e.g. `_client().models.list()`) is closed mid-request ("client has been closed").
    """
    from google import genai
    from google.genai import types

    return genai.Client(api_key=settings.GEMINI_API_KEY,
                        http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_SECONDS * 1000))


def _error_for(exc):
    """Turns a Gemini API error into a clear message (never exposing the key)."""
    code = getattr(exc, "code", None)
    text = f"{getattr(exc, 'status', '')} {getattr(exc, 'message', '')}".upper()
    if code == 429 or "RESOURCE_EXHAUSTED" in text:
        return AIRateLimited()
    if "DENIED ACCESS" in text:
        return NotConfigured("Google has denied this API key's project access to Gemini. Create a new key in a new "
                             "project at aistudio.google.com/apikey and put it in GEMINI_API_KEY in backend/.env.")
    if "API_KEY" in text or code in (401, 403):
        return NotConfigured("The Gemini API key was rejected. Check GEMINI_API_KEY in backend/.env.")
    if code == 404:
        retired = " It has been retired by Google." if "NO LONGER AVAILABLE" in text else ""
        return NotConfigured(f"The Gemini model '{settings.GEMINI_MODEL}' is not available.{retired} "
                             "Set GEMINI_MODEL in backend/.env (run `python manage.py check_ai` for options).")
    return AIEngineError()


def complete(system, messages, max_tokens=8192):  # Gemini 3 models count their reasoning in this budget
    """
    messages: [{role: 'user'|'assistant', content: str}], oldest first -> reply text.
    Raises NotConfigured / AIRateLimited / AIEngineError with user-readable messages.
    """
    if not is_configured():
        raise NotConfigured("The AI assistant is not connected. Set GEMINI_API_KEY in backend/.env.")
    from google.genai import errors, types

    contents = [
        types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
        for m in messages
    ]
    config = types.GenerateContentConfig(
        system_instruction=system, max_output_tokens=max_tokens, temperature=0.3,
        # Plain question/answer: no tools, so the SDK's automatic function calling is off
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    try:
        with _client() as client:
            response = client.models.generate_content(model=settings.GEMINI_MODEL, contents=contents, config=config)
    except errors.APIError as exc:
        log.error("Gemini API error %s: %s", getattr(exc, "code", "?"), getattr(exc, "message", exc))
        raise _error_for(exc) from exc
    except Exception as exc:  # network errors, timeouts
        log.exception("Gemini request failed")
        raise AIEngineError("The AI engine could not be reached. Check the internet connection and try again.") from exc

    text = (response.text or "").strip()
    if not text:
        reason = ""
        if response.candidates:
            reason = str(getattr(response.candidates[0], "finish_reason", "") or "")
        log.warning("Gemini returned no text (finish reason %s)", reason or "unknown")
        raise AIEngineError("The AI engine returned no answer for this question (it may have been filtered). Try rephrasing it.")
    return text


def available_models():
    """Gemini text models this key can list (names only). Listed doesn't always mean usable."""
    from google.genai import errors

    try:
        with _client() as client:
            # The pager fetches further pages while iterating, so read it fully inside the block
            return sorted(
                m.name.split("/")[-1] for m in client.models.list()
                if "generateContent" in (getattr(m, "supported_actions", None) or [])
                and not any(x in m.name for x in ("tts", "image", "embedding"))
            )
    except errors.APIError as exc:
        raise _error_for(exc) from exc
    except Exception as exc:  # network errors, timeouts
        raise AIEngineError("Google's Gemini service could not be reached. Check the internet connection.") from exc


def check_connection():
    """
    Used by `manage.py check_ai`: sends one tiny real request to the configured model, because
    a model can be listed yet retired or blocked for this key. Returns the model's reply text.
    """
    if not is_configured():
        raise NotConfigured("GEMINI_API_KEY is not set in backend/.env.")
    return complete("Reply with exactly one word.", [{"role": "user", "content": "Say OK."}], max_tokens=2048)
