"""MongoDB connection helpers (compat wrapper around infra layer)."""

from app.infra.mongo import get_client as get_client
from app.infra.mongo import get_database as get_database


def get_db():
    """
    FastAPI dependency-style generator that yields a shared database handle.
    """
    from app.infra.mongo import yield_database
    from app.config import settings

    yield from yield_database(settings.MONGODB_URI, settings.MONGODB_DB_NAME)
