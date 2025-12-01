"""Infrastructure helpers for MongoDB (compat with existing database module)."""

from buildguard_common.mongo import get_client, get_database, yield_database

__all__ = ["get_client", "get_database", "yield_database"]
