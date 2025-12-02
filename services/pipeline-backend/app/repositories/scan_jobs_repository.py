"""Scan jobs repository (infra layer)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import ReturnDocument

from app.models import ScanJobStatus
from app.repositories.base import MongoRepositoryBase


class ScanJobsRepository(MongoRepositoryBase):
    def create_scan_job(
        self,
        *,
        project_id: str,
        commit_sha: str,
        repository_url: str | None = None,
        repo_slug: str | None = None,
        project_key: str | None = None,
        component_key: str | None = None,
        sonar_instance: str | None = None,
        max_retries: int = 3,
        external_job_id: str | None = None,
    ) -> Dict[str, Any]:
        now = datetime.utcnow()
        payload = {
            "project_id": ObjectId(project_id),
            "commit_sha": commit_sha,
            "status": ScanJobStatus.pending.value,
            "retry_count": 0,
            "max_retries": max_retries,
            "repository_url": repository_url,
            "repo_slug": repo_slug,
            "project_key": project_key,
            "component_key": component_key,
            "sonar_instance": sonar_instance,
            "external_job_id": external_job_id,
            "created_at": now,
            "updated_at": now,
        }

        result = self.db[self.collections.scan_jobs_collection].insert_one(payload)
        payload["id"] = str(result.inserted_id)
        return payload

    def get_scan_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db[self.collections.scan_jobs_collection].find_one(
            {"_id": ObjectId(job_id)}
        )
        return self._serialize(doc)

    def update_scan_job(
        self, job_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        updates["updated_at"] = datetime.utcnow()
        doc = self.db[self.collections.scan_jobs_collection].find_one_and_update(
            {"_id": ObjectId(job_id)},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )
        return self._serialize(doc)

    def list_scan_jobs_paginated(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        if page < 1:
            page = 1
        skip = (page - 1) * page_size

        query: Dict[str, Any] = {}
        if project_id:
            query["project_id"] = ObjectId(project_id)
        if status:
            query["status"] = status

        collection = self.db[self.collections.scan_jobs_collection]
        total = collection.count_documents(query)
        cursor = (
            collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
        )
        items = [self._serialize(doc) for doc in cursor]
        return {"items": items, "total": total}

    def list_jobs_by_status(self, status: str) -> List[Dict[str, Any]]:
        cursor = (
            self.db[self.collections.scan_jobs_collection]
            .find({"status": status})
            .sort("created_at", -1)
        )
        return [self._serialize(doc) for doc in cursor]

    def list_scan_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = (
            self.db[self.collections.scan_jobs_collection]
            .find()
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._serialize(doc) for doc in cursor]

    def claim_job(
        self, status: str, worker_id: str, grace_seconds: int = 300
    ) -> Optional[Dict[str, Any]]:
        now = datetime.utcnow()
        lock_until = now + timedelta(seconds=grace_seconds)

        doc = self.db[self.collections.scan_jobs_collection].find_one_and_update(
            {"status": status},
            {
                "$set": {
                    "status": ScanJobStatus.running.value,
                    "last_worker_id": worker_id,
                    "last_started_at": now,
                    "lock_until": lock_until,
                    "updated_at": now,
                }
            },
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
        return self._serialize(doc) if doc else None

    def find_job_by_component_key(self, component_key: str) -> Optional[Dict[str, Any]]:
        doc = self.db[self.collections.scan_jobs_collection].find_one(
            {"component_key": component_key}
        )
        return self._serialize(doc)

    def find_stalled_jobs(self, older_than_minutes: int = 10) -> List[Dict[str, Any]]:
        cutoff = datetime.utcnow() - timedelta(minutes=older_than_minutes)
        cursor = self.db[self.collections.scan_jobs_collection].find(
            {
                "status": ScanJobStatus.running.value,
                "last_started_at": {"$lt": cutoff},
            }
        )
        return [self._serialize(doc) for doc in cursor]


__all__ = ["ScanJobsRepository"]
