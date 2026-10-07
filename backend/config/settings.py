"""
HIPA MASALA backend settings.

Every secret and environment-specific value comes from environment variables,
loaded from backend/.env in development (see .env.example).
"""
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and (value is None or value == ""):
        raise ImproperlyConfigured(f"Environment variable {name} is required (see .env.example).")
    return value


def env_bool(name, default=False):
    return str(env(name, str(default))).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in str(env(name, default)).split(",") if item.strip()]


# --- Core -------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # HIPA MASALA apps
    "apps.core",
    "apps.accounts",
    "apps.system",
    "apps.customers",
    "apps.inventory",
    "apps.sales",
    "apps.purchase",
    # Retired Production module: migration history only (its last migration drops the old tables)
    "apps.legacy_production",
    "apps.marketing",
    "apps.supply_chain",
    "apps.quality",
    "apps.finance",
    "apps.reports",
    "apps.ai_assistant",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database (Supabase Postgres) ---------------------------------------------
# Django talks to Supabase's Postgres directly. SUPABASE_DB_URL is the connection string from
# Supabase → Connect → "Session pooler" (postgresql://postgres.<ref>:<password>@<host>:5432/postgres).
def _database_from_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("SUPABASE_DB_URL must start with postgresql:// (see .env.example).")
    options = dict(parse_qsl(parts.query))
    options.setdefault("sslmode", env("DB_SSLMODE", "require"))
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parts.path.lstrip("/")) or "postgres",
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or 5432),
        "OPTIONS": options,
        "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
        # Supabase's transaction pooler (port 6543) can't hold server-side cursors open.
        "DISABLE_SERVER_SIDE_CURSORS": parts.port == 6543,
        "TEST": {"NAME": env("DB_TEST_NAME", "test_hipa_masala")},
    }


DATABASES = {"default": _database_from_url(env("SUPABASE_DB_URL", required=True))}

# Supabase project API settings (Supabase → Project Settings → API). The backend reaches the
# database through SUPABASE_DB_URL; these are for Supabase services such as Storage.
SUPABASE_URL = env("SUPABASE_URL", "")
SUPABASE_ANON_KEY = env("SUPABASE_ANON_KEY", "")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TEST_RUNNER = "config.test_runner.SupabaseTestRunner"
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Locale -----------------------------------------------------------------
LANGUAGE_CODE = "en-in"
TIME_ZONE = env("TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

# --- Files ------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
BACKUP_DIR = Path(env("BACKUP_DIR", str(BASE_DIR / "backups")))
PG_DUMP_PATH = env("PG_DUMP_PATH", "pg_dump")
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# --- REST API ---------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.VersionedJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {"login": env("LOGIN_THROTTLE_RATE", "10/min"), "password_reset": "5/hour",
                               "ai_chat": env("AI_CHAT_THROTTLE_RATE", "20/min")},
    # How many proxies (e.g. nginx) sit in front of Django. 0 = none: the X-Forwarded-For header is ignored,
    # because anyone can fake it to dodge the rate limits. Set it only when the server is behind a proxy.
    "NUM_PROXIES": int(env("NUM_PROXIES", "0")),
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    # The frontend uses ?format=pdf|xlsx|csv for report files, so DRF must not treat it as a renderer switch
    "URL_FORMAT_OVERRIDE": None,
}

SIMPLE_JWT = {
    # The web app keeps only the access token, so it lasts a working day by default
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "480"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --- CORS (the React app runs on its own origin in development) -----------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_EXPOSE_HEADERS = ["Content-Disposition"]  # the frontend reads download file names
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", ",".join(CORS_ALLOWED_ORIGINS))

# Links in emails (password reset) point here
FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173").rstrip("/")

# --- Email ------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
# Seconds to wait for the mail server, so a stuck server can't hang a request
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "HIPA MASALA <no-reply@localhost>")

# --- AI engine: Google Gemini (optional; the AI Assistant reports "not connected" until set) ---
# The key stays on the server; the React app only talks to /api/v1/ai/.
GEMINI_API_KEY = env("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
GEMINI_TIMEOUT_SECONDS = int(env("GEMINI_TIMEOUT_SECONDS", "60"))

# --- Production hardening ------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "3600"))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
        # The Gemini SDK's HTTP library logs every request at INFO; keep only warnings and errors
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
        "google_genai": {"level": "WARNING"},
    },
}
