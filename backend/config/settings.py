"""
Django settings for the Mystery Auctions ft_transcendence project.

All secrets and environment-specific values come from the environment
(.env via docker-compose). Nothing secret is hard-coded here.
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY is required. Copy .env.example to .env and set it.")

DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "https://localhost:8443")

AUTH_USER_MODEL = "accounts.CustomUser"

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework_simplejwt.token_blacklist",
    # Third party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    # Project apps
    "apps.common",
    "apps.accounts",
    "apps.products",
    "apps.auctions",
    "apps.orders",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.RequestIDMiddleware",
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
ASGI_APPLICATION = "config.asgi.application"

# Channels / WebSockets
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# Cache (presence, throttles)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "transcendence_db"),
        "USER": os.getenv("POSTGRES_USER", "transcendence_user"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Upload validation (also enforced per-file in serializers)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
AVATAR_MAX_SIZE = 2 * 1024 * 1024
IMAGE_MAX_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# Security
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # read by the frontend to send X-CSRFToken
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_SSL_REDIRECT = False  # Nginx terminates TLS and sends X-Forwarded-Proto
    SILENCED_SYSTEM_CHECKS = ["security.W008"]

# CORS (the SPA is served by the same origin via Nginx; kept for dev flexibility)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS", "https://localhost:8443")
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "x-csrftoken",
    "x-requested-with",
    "x-api-key",
]

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "apps.common.authentication.CookieJWTAuthentication",
        "apps.common.authentication.ApiKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",
        "login": "5/min",
        # Keep production abuse protection strict while allowing local test
        # environments to opt into a larger, still finite allowance.
        "register": os.getenv("REGISTER_THROTTLE_RATE", "5/hour"),
        "two_fa": "5/min",
        "password_reset": "5/hour",
        "bids": "30/min",
        "public_api": "60/min",
        "imports": "10/hour",
    },
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# SimpleJWT (tokens travel only in Secure HttpOnly cookies)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", 15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", 7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ACCESS_COOKIE": "access_token",
    "REFRESH_COOKIE": "refresh_token",
    # The same HttpOnly access token authenticates REST requests and the
    # authenticated Channels endpoint at /ws/auth/.
    "ACCESS_COOKIE_PATH": "/",
    "REFRESH_COOKIE_PATH": "/api/accounts/auth/",
    "COOKIE_SECURE": not DEBUG,
    "COOKIE_HTTPONLY": True,
    "COOKIE_SAMESITE": "Lax",
    "BLACKLIST_TOKEN_CHECKS": ["access", "refresh"],
}

# drf-spectacular / OpenAPI
SPECTACULAR_SETTINGS = {
    "TITLE": "Mystery Auctions API",
    "DESCRIPTION": (
        "Live mystery-auction platform API. Cookie-based JWT authentication "
        "(access_token / refresh_token cookies), CSRF for unsafe methods, and a "
        "rate-limited public API key for read endpoints under /api/v1/."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Function-based internal endpoints intentionally use hand-written response
    # envelopes. Public API operations carry explicit schemas; do not turn
    # drf-spectacular's best-effort inference notices into Django deploy checks.
    "DISABLE_ERRORS_AND_WARNINGS": True,
    "ENABLE_DJANGO_DEPLOY_CHECK": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "AuctionEventStatusEnum": "apps.auctions.models.AuctionEventStatus",
        "AuctionLotStatusEnum": "apps.auctions.models.AuctionLotStatus",
        "BidStatusEnum": "apps.auctions.models.BidStatus",
        "BidRejectionReasonEnum": "apps.auctions.models.RejectionReason",
        "OrderStatusEnum": "apps.orders.models.OrderStatus",
        "PaymentStatusEnum": "apps.orders.models.PaymentStatus",
    },
}

# Celery
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "auction-ticks": {
        "task": "apps.auctions.tasks.auction_tick",
        "schedule": env_int("AUCTION_TICK_SECONDS", 30),
    },
}

# Email (console backend by default; SMTP when configured)
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
).strip() or "django.core.mail.backends.console.EmailBackend"
if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.example.com")
    EMAIL_PORT = env_int("EMAIL_PORT", 587)
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@mystery-auctions.local")

# Auction business rules
# lets say i want to change the min rule time in here 
# chang this line from 3600 == 1 hour to 1200 = 20 min
# or in the .env file do this ==> AUCTION_MIN_START_DELAY=1200

AUCTION_MIN_START_DELAY = env_int("AUCTION_MIN_START_DELAY", 3600)  # its in seconds adds up to 1 hour
AUCTION_CLOSING_SOON_MINUTES = env_int("AUCTION_CLOSING_SOON_MINUTES", 5)
AUCTION_EDITABLE_LEAD_MINUTES = env_int("AUCTION_EDITABLE_LEAD_MINUTES", 1440)
MIN_EVENT_DURATION = timedelta(minutes=env_int("AUCTION_MIN_EVENT_MINUTES", 30))
MAX_EVENT_DURATION = timedelta(hours=env_int("AUCTION_MAX_EVENT_HOURS", 24))

# Frontend URLs used in emails
PASSWORD_RESET_FRONTEND_URL = os.getenv("PASSWORD_RESET_FRONTEND_URL", "https://localhost:8443")
EMAIL_VERIFICATION_FRONTEND_URL = os.getenv(
    "EMAIL_VERIFICATION_FRONTEND_URL", "https://localhost:8443/verify-email"
)

# Demo seeding (never on by default without explicit env)
SEED_DEMO = env_bool("SEED_DEMO", False)

# Logging with request IDs and redaction
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact": {"()": "apps.common.middleware.RedactingFilter"},
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} request={request_id} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["redact"],
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "channels": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
PRIVATE_UPLOAD_ROOT = BASE_DIR / "private_uploads"
ATTACHMENT_MAX_SIZE = env_int("ATTACHMENT_MAX_SIZE", 10 * 1024 * 1024)
