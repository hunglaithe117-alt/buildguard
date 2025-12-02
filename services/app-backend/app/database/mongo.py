"""MongoDB connection helpers (compat wrapper around infra layer)."""

from buildguard_common.mongo import yield_database
from app.config import settings


def get_db():
    yield from yield_database(settings.MONGODB_URI, settings.MONGODB_DB_NAME)
