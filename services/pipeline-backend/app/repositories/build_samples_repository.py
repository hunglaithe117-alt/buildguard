"""Build samples repository (infra layer)."""

from __future__ import annotations

from typing import Any, Dict

from bson import ObjectId

from app.repositories.base import MongoRepositoryBase


class BuildSamplesRepository(MongoRepositoryBase):
    def update_build_sample(self, build_id: str, updates: Dict[str, Any]) -> None:
        self.db[self.collections.build_samples_collection].update_one(
            {"_id": ObjectId(build_id)}, {"$set": updates}
        )


__all__ = ["BuildSamplesRepository"]
