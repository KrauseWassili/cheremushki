import os
from datetime import timedelta
from pathlib import Path
from typing import List, Tuple

import environ
from celery.schedules import crontab
from corsheaders.defaults import default_methods
from django.templatetags.static import static

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

# --- Take environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, "../.env"))
SECRET_KEY: str = env("SECRET_KEY")
DEBUG: bool = env("DEBUG")
ALLOWED_HOSTS: List[str] = env("ALLOWED_HOSTS").split(",")

DJANGO_APPS: Tuple[str, ...] = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
)

THIRD_PARTY_APPS: Tuple[str, ...] = (
    "rest_framework",
    "daphne",
    "rest_framework.authtoken",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
)

LOCAL_APPS: Tuple[str, ...] = ("apps.accounts", "apps.bot")
INSTALLED_APPS = THIRD_PARTY_APPS + DJANGO_APPS + LOCAL_APPS

AUTH_USER_MODEL = "accounts.CustomUser"

MIDDLEWARE: List[str] = [
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
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DATABASE_NAME"),
        "USER": env("DATABASE_USER"),
        "PASSWORD": env("DATABASE_PASSWORD"),
        "HOST": env("DATABASE_HOST"),
        "PORT": env("DATABASE_PORT"),
    }
}

UNFOLD = {
    "SITE_TITLE": "Webseite Verwaltung",
    "SITE_DROPDOWN": [
        {
            "icon": "diamond",
            "title": "Cheremushki Admin",
            "link": "http://localhost:3000",
        },
    ],
    "SITE_URL": "http://localhost:3000",
    "SITE_LOGO": {
        "light": lambda request: static("image/logo.webp"),
        "dark": lambda request: static("image/logo.webp"),
    },
    "SITE_SYMBOL": "speed",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": False,
    "THEME": "light",
    "LOGIN": {
        "image": lambda request: static("image/home-header.webp"),
    },
    "BORDER_RADIUS": "6px",
    "COLORS": {
        # Sand (Sekundär) – frontend --color-sand-*
        "base": {
            "50": "#fafaf9",
            "100": "#f5f5f4",
            "200": "#e7e5e4",
            "300": "#d6d3d1",
            "400": "#a8a29e",
            "500": "#78716c",
            "600": "#57534e",
            "700": "#44403c",
            "800": "#292524",
            "900": "#1c1917",
            "950": "#0c0a09",
        },
        # Gold (Primär) – frontend --color-gold-*
        "primary": {
            "50": "#faf7f2",
            "100": "#f5ede0",
            "200": "#ead9c0",
            "300": "#dfc5a0",
            "400": "#d4a373",
            "500": "#c49363",
            "600": "#b38353",
            "700": "#8f6942",
            "800": "#6b4f32",
            "900": "#473521",
            "950": "#2a1f14",
        },
        # Textfarben – frontend body, nav, placeholders
        "font": {
            "subtle-light": "#78716c",
            "subtle-dark": "#a8a29e",
            "default-light": "#44403c",
            "default-dark": "#d6d3d1",
            "important-light": "#1c1917",
            "important-dark": "#f5f5f4",
        },
    },
}
# --- Telegram Bot -------------------------------------------------- #
TELEGRAM_BOT_TOKEN = env.str("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID = env.str("TELEGRAM_CHAT_ID", default="")
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET")

# --- Cors ----------------------------------------------------------- #
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = "/api/.*"

CORS_ALLOW_METHODS = default_methods

CORS_ALLOWED_ORIGINS: List[str] = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)

# ------ Celery / Redis settings ------------------------------------------------------ #
REDIS_URL = env.str("REDIS_URL", default="")

CELERY_TIMEZONE = "Europe/Berlin"
CELERY_BROKER_URL = env("DJANGO_CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("DJANGO_CELERY_RESULT_BACKEND")
CELERY_TASK_ALWAYS_EAGER = env.bool("DJANGO_CELERY_TASK_ALWAYS_EAGER", default=False)

CELERY_CACHE_BACKEND = "default"
CELERY_TASK_CREATE_MISSING_QUEUES = True
CELERY_RETRY_DELAY = 15
CELERY_RETRY_MAX_TIMES = 15  # 15 retries

# Leichte Tasks laufen auf der "default"-Queue, rechenintensive auf "generation".
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "apps.bot.tasks.email.*": {"queue": "default"},
    "apps.bot.tasks.telegram_user.*": {"queue": "default"},
    "apps.*.tasks.generation.*": {"queue": "generation"},
}

CELERY_BEAT_SCHEDULE = {
    "poll-telegram-updates": {
        "task": "apps.bot.tasks.telegram_user.poll_telegram_updates_task",
        "schedule": 10.0,  # alle 10 Sekunden
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "apps.accounts.services.user_service.password_validator.EntirelyAlphabeticPasswordValidator",
    },
    {
        "NAME": "apps.accounts.services.user_service.password_validator.EntirelyNonCapitalLetterPasswordValidator",
    },
    {
        "NAME": "apps.accounts.services.user_service.password_validator.NoSmallLetterPasswordValidator",
    },
    {
        "NAME": "apps.accounts.services.user_service.password_validator.EntirelyNoneSpecialCharactersPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "de-DE"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / env("DJANGO_STATIC_ROOT", default="staticfiles")
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / env("DJANGO_MEDIA_ROOT", default="media")

API_DOCS_ENABLED: bool = env.bool("API_DOCS_ENABLED", default=True)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "PAGE_SIZE": 100,
    # --- To enable filtering, search and ordering in DRF ---------------- #
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # Rate limiting setting that restricts access Telegram Login View.
    # It prevents a client from sending too many requests in a short period of time.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "contact": "5/hour",  # Spam protection for contact form submissions
    },
}

SPECTECULAR_SETTINGS = {
    "TITLE": "Cheremushki API",
    "DESCRIPTION": "Cheremushki API Documentation",
    "VERSION": "0.0.0",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(minutes=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "VERIFYING_KEY": SECRET_KEY,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
    "SIGNING_KEY": SECRET_KEY,
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@cheremushki.de")
if DEBUG:
    EMAIL_HOST = env("EMAIL_HOST", default="mailcatcher")
    EMAIL_HOST_USER = ""
    EMAIL_HOST_PASSWORD = ""
    EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
    EMAIL_USE_TLS = False
