"""Mongo repository base for pipeline backend (infra layer)."""

from __future__ import annotations

from typing import Any, Dict

from buildguard_common.mongo import get_client

from app.core.config import settings


class MongoRepositoryBase:
    """Base class that provides the Mongo client, database and helpers."""

    def __init__(self) -> None:
        self.client = get_client(settings.mongo.uri, **settings.mongo.options)
        self.db = self.client[settings.mongo.database]
        self.collections = settings.storage

    @staticmethod
    def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
        if not doc:
            return doc
        doc = {**doc}
        if "_id" in doc:
            doc["id"] = str(doc.pop("_id"))
        return doc

    def transaction(self):
        """Return a client session context manager for transactions."""
        return self.client.start_session()
