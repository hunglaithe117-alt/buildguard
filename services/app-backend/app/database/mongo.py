"""MongoDB connection helpers (compat wrapper around infra layer)."""

from buildguard_common.mongo import get_database as _get_database, yield_database
from app.config import settings


def get_database():
    """Return a MongoDB database handle (non-dependency use)."""
    return _get_database(settings.MONGODB_URI, settings.MONGODB_DB_NAME)


def get_db():
    """FastAPI dependency that yields a database handle."""
    yield from yield_database(settings.MONGODB_URI, settings.MONGODB_DB_NAME)
