"""Repository for imported repositories (infra layer)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.domain.entities import ImportedRepository, ImportStatus
from app.infra.repositories.base import BaseRepository


class ImportedRepositoryRepository(BaseRepository[ImportedRepository]):
    def __init__(self, db):
        super().__init__(db, "imported_repositories", ImportedRepository)
        self.collection.create_index([("user_id", 1), ("full_name", 1)], unique=True)

    def get(self, repo_id: str | ObjectId) -> Optional[ImportedRepository]:
        return self.find_by_id(repo_id)

    def find_by_full_name(self, user_id: str | ObjectId, full_name: str) -> Optional[ImportedRepository]:
        return self.find_one(
            {"user_id": self._to_object_id(user_id), "full_name": full_name}
        )

    def upsert_repository(self, query: Dict[str, Any], data: Dict[str, Any]) -> ImportedRepository:
        now = datetime.now(timezone.utc)
        update = {"$set": data | {"updated_at": now}, "$setOnInsert": {"created_at": now}}
        self.collection.update_one(query, update, upsert=True)
        return self.find_one(query)

    def update(self, repo_id: str | ObjectId, data: Dict[str, Any]) -> Optional[ImportedRepository]:
        data["updated_at"] = datetime.now(timezone.utc)
        return super().update(repo_id, data)

    def list_by_user(self, user_id: str | ObjectId, status: Optional[ImportStatus] = None) -> List[ImportedRepository]:
        query: Dict[str, Any] = {"user_id": self._to_object_id(user_id)}
        if status:
            query["import_status"] = status
        return self.find_many(query, sort=[("created_at", -1)])

    def find_by_installation(self, installation_id: str) -> List[ImportedRepository]:
        return self.find_many({"installation_id": installation_id})


__all__ = ["ImportedRepositoryRepository"]
