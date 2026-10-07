"""Environment-driven configuration."""
from __future__ import annotations

import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://easygo:easygo@db:5432/easygo"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

    # Fernet key for encrypting channel credentials/tokens at rest (spec §4.1).
    FERNET_KEY = os.environ.get("FERNET_KEY") or ""

    MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/data/media")

    # Public base URL used to register channel webhooks (e.g. a tunnel or domain).
    # Example: https://abc123.ngrok-free.app  (no trailing slash)
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")

    # Meta (Messenger/Instagram) app-level config — one Meta app, many Pages.
    META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
    META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "")
    META_GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v21.0")

    # Email alerts (NT-3) — optional; disabled when SMTP_HOST is empty.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    MAIL_FROM = os.environ.get("MAIL_FROM", "easygo@localhost")

    # Web Push (NT-2) — optional; disabled when keys are empty.
    # Generate: python -c "from py_vapid import Vapid01;v=Vapid01();v.generate_keys();import base64;print(base64.urlsafe_b64encode(v.private_pem()).decode())"
    # (or use the web-push CLI). Store the base64url public/private keys here.
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@localhost")

    # Outbound HTTP timeout (seconds) for Telegram / DeepSeek calls.
    HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "30"))

    # Session cookie hardening (spec §10 — security).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    # First admin, created by `flask seed`.
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@easygo.local")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin12345")
    ADMIN_NAME = os.environ.get("ADMIN_NAME", "مدير النظام")


class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


_CONFIGS = {"dev": DevConfig, "prod": ProdConfig}


def get_config(name: str | None = None) -> type[Config]:
    name = name or os.environ.get("FLASK_ENV", "dev")
    return _CONFIGS.get(name, DevConfig)
