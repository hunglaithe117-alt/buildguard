"""Failed commits repository (infra layer)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import ReturnDocument

from buildguard_common.repositories.base import MongoRepositoryBase


class FailedCommitRepository(MongoRepositoryBase):
    def insert_failed_commit(
        self,
        *,
        payload: dict,
        reason: str,
        config_override: Optional[str] = None,
        config_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow()
        doc = {
            "payload": payload,
            "reason": reason,
            "status": "pending",
            "config_override": config_override,
            "config_source": config_source,
            "counted": True,
            "created_at": now,
            "updated_at": now,
        }
        result = self.db[self.collections.failed_commits_collection].insert_one(doc)
        doc["id"] = str(result.inserted_id)
        return doc

    def list_failed_commits(
        self, project_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if project_id:
            query["payload.project_id"] = project_id
        cursor = (
            self.db[self.collections.failed_commits_collection]
            .find(query)
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._serialize(doc) for doc in cursor]

    def list_failed_commits_paginated(
        self,
        project_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        if page < 1:
            page = 1
        skip = (page - 1) * page_size
        query: Dict[str, Any] = {}
        if project_id:
            query["payload.project_id"] = project_id

        collection = self.db[self.collections.failed_commits_collection]
        total = collection.count_documents(query)
        cursor = (
            collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
        )
        items = [self._serialize(doc) for doc in cursor]
        return {"items": items, "total": total}

    def get_failed_commit(self, record_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db[self.collections.failed_commits_collection].find_one(
            {"_id": ObjectId(record_id)}
        )
        return self._serialize(doc)

    def get_failed_commit_by_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db[self.collections.failed_commits_collection].find_one(
            {"payload.job_id": job_id}
        )
        return self._serialize(doc)

    def update_failed_commit(
        self, record_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        updates["updated_at"] = datetime.utcnow()
        doc = self.db[self.collections.failed_commits_collection].find_one_and_update(
            {"_id": ObjectId(record_id)},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        return self._serialize(doc)

    def count_by_job_id(self, job_id: str) -> int:
        return self.db[self.collections.failed_commits_collection].count_documents(
            {"payload.job_id": job_id, "counted": True}
        )

    def count_by_project_id(self, project_id: str) -> int:
        return self.db[self.collections.failed_commits_collection].count_documents(
            {"payload.project_id": project_id, "counted": True}
        )


__all__ = ["FailedCommitRepository"]
