"""
Django settings for the KSP Investigative Intelligence System (spec §17).

Env via python-dotenv per §3.1 pins. JWT_SECRET/SECRET_KEY fail HARD at
startup when unset — no dev defaults (§0.4, §17).
"""
from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _raw(name: str, default: str | None, required: bool) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        if required:
            raise ImproperlyConfigured(f"{name} is required and not set (spec §0.4 fail loud)")
        return default
    return value


def env_str(name: str, default: str | None = None, *, required: bool = False) -> str | None:
    return _raw(name, default, required)


def env_bool(name: str, default: bool = False) -> bool:
    value = _raw(name, None, False)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes")


def env_int(name: str, default: int = 0) -> int:
    value = _raw(name, None, False)
    if value is None:
        return default
    return int(value)


def env_list(name: str, default: list | None = None) -> list:
    value = _raw(name, None, False)
    if value is None:
        return list(default or [])
    return [v.strip() for v in value.split(",") if v.strip()]


SECRET_KEY = env_str("SECRET_KEY", required=True)
DEBUG = env_bool("DEBUG", default=False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "apps.accounts",
    "apps.fir",
    "apps.audit",
    "apps.intel",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.JWTAuthMiddleware",
    "apps.audit.middleware.RequestAuditMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("DB_NAME", required=True),
        "USER": env_str("DB_USER", required=True),
        "PASSWORD": env_str("DB_PASSWORD", required=True),
        "HOST": env_str("DB_HOST", default="postgres"),
        "PORT": env_int("DB_PORT", default=5432),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.CustomUser"

# ── JWT (spec §17: HS256, fail-hard secret, 30 min access / 12 h refresh) ──
JWT_SECRET = env_str("JWT_SECRET", required=True)
JWT_ALGORITHM = "HS256"
JWT_ACCESS_MINUTES = env_int("JWT_ACCESS_MINUTES", default=30)
JWT_REFRESH_HOURS = env_int("JWT_REFRESH_HOURS", default=12)

# ── CORS ──────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# ── RAG service (§2.1: Django only authenticates, authorizes, audits,
#    attaches scope, and proxies the stream — never builds prompts) ─────────
RAG_URL = env_str("RAG_URL", default="http://rag:9000")
RAG_API_KEY = env_str("RAG_API_KEY", default="")
GRAPH_RAG_TIMEOUT = env_int("GRAPH_RAG_TIMEOUT", default=300)

# ── Neo4j (FIR CRUD reads the evidentiary domain graph, §2.1/§4) ──────────
NEO4J_URI = env_str("NEO4J_URI", default="bolt://neo4j:7687")
NEO4J_USER = env_str("NEO4J_USER", default="neo4j")
NEO4J_PASSWORD = env_str("NEO4J_PASSWORD", default="")
NEO4J_DATABASE = env_str("NEO4J_DATABASE", default="neo4j")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"format": '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
