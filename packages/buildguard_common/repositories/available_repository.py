"""Repository for available repositories (infra layer)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from buildguard_common.models.available_repository import AvailableRepository
from buildguard_common.repositories.base import BaseRepository, CollectionName


class AvailableRepositoryRepository(BaseRepository[AvailableRepository]):
    def __init__(self, db):
        super().__init__(db, CollectionName.AVAILABLE_REPOSITORIES, AvailableRepository)
        self.collection.create_index([("user_id", 1), ("full_name", 1)], unique=True)

    def list_by_user(
        self, user_id: str | ObjectId, filters: Optional[Dict[str, Any]] = None
    ) -> List[AvailableRepository]:
        query = {"user_id": self._to_object_id(user_id)}
        if filters:
            query.update(filters)
        return self.find_many(query, sort=[("full_name", 1)])

    def upsert_available_repo(
        self,
        user_id: str | ObjectId,
        repo_data: Dict[str, Any],
        installation_id: Optional[str] = None,
    ) -> AvailableRepository:
        now = datetime.now(timezone.utc)
        user_oid = self._to_object_id(user_id)
        filter_query = {"user_id": user_oid, "full_name": repo_data["full_name"]}
        update_doc = {
            "user_id": user_oid,
            "full_name": repo_data["full_name"],
            "github_id": repo_data["id"],
            "private": repo_data["private"],
            "html_url": repo_data["html_url"],
            "description": repo_data.get("description"),
            "default_branch": repo_data.get("default_branch", "main"),
            "language": repo_data.get("language"),
            "metadata": repo_data,
            "updated_at": now,
        }
        if installation_id:
            update_doc["installation_id"] = installation_id
        self.collection.update_one(filter_query, {"$set": update_doc}, upsert=True)
        return self.find_one(filter_query)

    def delete_by_user(self, user_id: str | ObjectId):
        self.collection.delete_many({"user_id": self._to_object_id(user_id)})

    def discover_available_repositories(
        self, user_id: str | ObjectId, q: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        filters = {
            "user_id": self._to_object_id(user_id),
            "imported": {"$ne": True},
            "installation_id": {"$ne": None},
        }
        if q:
            filters["full_name"] = {"$regex": q, "$options": "i"}

        repos = self.collection.find(
            filter=filters, sort=[("full_name", 1)], limit=limit
        )
        items = []
        for repo in repos:
            full_name = repo.get("full_name")
            if not full_name:
                continue
            items.append(
                {
                    "full_name": full_name,
                    "description": repo.get("description"),
                    "default_branch": repo.get("default_branch"),
                    "private": bool(repo.get("private")),
                    "owner": full_name.split("/")[0],
                    "installation_id": repo.get("installation_id"),
                    "html_url": repo.get("html_url"),
                }
            )
        return items

    def delete_stale_available_repositories(
        self, user_id: str, active_full_names: List[str]
    ):
        self.collection.delete_many(
            {
                "user_id": self._to_object_id(user_id),
                "full_name": {"$nin": active_full_names},
            }
        )


__all__ = ["AvailableRepositoryRepository"]
