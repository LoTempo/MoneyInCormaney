import os
from datetime import timedelta

from dotenv import load_dotenv


load_dotenv()


def env_flag(name, default="false"):
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer.") from error


class Config:
    """Base settings for the Flask application."""

    APP_ENV = os.getenv("APP_ENV", "development").lower()
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-secret-key")
    DATABASE_URL = os.getenv("DATABASE_URL") or None
    DATABASE_ADMIN_URL = os.getenv("DATABASE_ADMIN_URL") or None
    DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
    DATABASE_PORT = env_int("DATABASE_PORT", 5432)
    DATABASE_NAME = os.getenv("DATABASE_NAME", "family_budget")
    DATABASE_USER = os.getenv("DATABASE_USER", "family_budget_user")
    DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
    DATABASE_CONNECT_TIMEOUT = env_int("DATABASE_CONNECT_TIMEOUT", 5)
    DEBUG = env_flag("FLASK_DEBUG")
    SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
    SERVER_PORT = env_int("SERVER_PORT", 5000)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
