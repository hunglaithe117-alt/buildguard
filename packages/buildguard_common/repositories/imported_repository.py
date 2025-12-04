"""Repository for imported repositories (infra layer)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from bson import ObjectId

from buildguard_common.models.imported_repository import (
    ImportedRepository,
    ImportStatus,
)
from buildguard_common.repositories.base import BaseRepository, CollectionName


class ImportedRepositoryRepository(BaseRepository[ImportedRepository]):
    def __init__(self, db):
        # Keep collection name aligned with app usage (`db.repositories`) so all
        # services read/write the same documents.
        super().__init__(db, CollectionName.REPOSITORIES, ImportedRepository)
        self.collection.create_index([("user_id", 1), ("full_name", 1)], unique=True)

    def get(self, repo_id: Union[str, ObjectId]) -> Optional[ImportedRepository]:
        return self.find_by_id(repo_id)

    def find_by_full_name(
        self, user_id: Union[str, ObjectId], full_name: str
    ) -> Optional[ImportedRepository]:
        return self.find_one(
            {"user_id": self._to_object_id(user_id), "full_name": full_name}
        )

    def upsert_repository(
        self, query: Dict[str, Any], data: Dict[str, Any]
    ) -> ImportedRepository:
        now = datetime.now(timezone.utc)
        update = {
            "$set": {**data, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        }
        self.collection.update_one(query, update, upsert=True)
        return self.find_one(query)

    def update(
        self, repo_id: Union[str, ObjectId], data: Dict[str, Any]
    ) -> Optional[ImportedRepository]:
        data["updated_at"] = datetime.now(timezone.utc)
        return super().update(repo_id, data)

    def update_repository(
        self, repo_id: Union[str, ObjectId], data: Dict[str, Any]
    ) -> Optional[ImportedRepository]:
        return self.update(repo_id, data)

    def get_repository(
        self, repo_id: Union[str, ObjectId]
    ) -> Optional[ImportedRepository]:
        return self.get(repo_id)

    def list_by_user(
        self,
        user_id: Union[str, ObjectId],
        status: Optional[ImportStatus] = None,
        skip: int = 0,
        limit: Optional[int] = None,
        query: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[ImportedRepository], int]:
        """
        List repositories for a user with optional status filter and pagination.
        Returns (items, total) for UI pagination.
        """
        filters: Dict[str, Any] = {"user_id": self._to_object_id(user_id)}
        if status:
            filters["import_status"] = (
                status.value if isinstance(status, ImportStatus) else status
            )
        if query:
            filters.update(query)

        total = self.collection.count_documents(filters)
        items = self.find_many(
            filters, sort=[("created_at", -1)], skip=skip, limit=limit
        )
        return items, total

    def find_by_installation(self, installation_id: str) -> List[ImportedRepository]:
        return self.find_many({"installation_id": installation_id})


__all__ = ["ImportedRepositoryRepository"]
