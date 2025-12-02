"""Shared MongoDB helpers for BuildGuard services."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from pymongo import MongoClient

_clients: Dict[Tuple[str, frozenset], MongoClient] = {}


def get_client(uri: str, **kwargs: Any) -> MongoClient:
    """
    Return a cached MongoClient keyed by URI and options.
    This avoids creating many clients across services and tasks.
    """
    key = (uri, frozenset(kwargs.items()))
    if key not in _clients:
        _clients[key] = MongoClient(uri, **kwargs)
    return _clients[key]


def get_database(uri: str, db_name: str, **kwargs: Any):
    """Convenience helper to fetch a database handle."""
    client = get_client(uri, **kwargs)
    return client[db_name]


def yield_database(uri: str, db_name: str, **kwargs: Any):
    """
    Dependency helper for FastAPI/Celery tasks to yield a database.
    Keeps lifecycle consistent while letting PyMongo manage pooling.
    """
    db = get_database(uri, db_name, **kwargs)
    try:
        yield db
    finally:
        # Clients are cached; no explicit close here.
        pass
