import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    """Base settings for the Flask application."""

    SECRET_KEY = os.getenv("SECRET_KEY", "development-secret-key")
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/family_budget",
    )
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
