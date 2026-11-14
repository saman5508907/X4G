import os
from urllib.parse import urlparse

def normalize_database_url(value: str) -> str:
    # Railway may provide postgres://; SQLAlchemy expects postgresql+psycopg://.
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value

DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./paypilot.db"))
SECRET_KEY = os.getenv("SECRET_KEY", "")
APP_ENV = os.getenv("APP_ENV", "development").lower()
COOKIE_SECURE = APP_ENV == "production"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]
SESSION_MAX_AGE = 60 * 60 * 8
