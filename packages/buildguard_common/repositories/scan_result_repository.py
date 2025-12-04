"""Repository for scan results (infra layer)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pymongo import ReturnDocument

from buildguard_common.models.scan_result import ScanResult
from buildguard_common.repositories.base import BaseRepository, CollectionName


class ScanResultRepository(BaseRepository[ScanResult]):
    def __init__(self, db):
        super().__init__(db, CollectionName.SCAN_RESULTS, ScanResult)

    def upsert_by_job(self, job_id: Union[str, ObjectId], data: Dict) -> ScanResult:
        filter_query = {"job_id": self._to_object_id(job_id)}
        self.collection.update_one(filter_query, {"$set": data}, upsert=True)
        return self.find_one(filter_query)

    def list_by_repo(
        self, repo_id: Union[str, ObjectId], skip: int = 0, limit: int = 20
    ) -> List[ScanResult]:
        return self.find_many(
            {"repo_id": self._to_object_id(repo_id)},
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    def count_by_repo(self, repo_id: Union[str, ObjectId]) -> int:
        return self.collection.count_documents({"repo_id": self._to_object_id(repo_id)})

    # Methods from pipeline-backend
    def upsert_result(
        self,
        *,
        job_id: str,
        project_id: str,
        metrics: Dict[str, Any],
        sonar_project_key: str,
    ) -> Dict[str, Any]:
        payload = {
            "job_id": ObjectId(job_id),
            "project_id": ObjectId(project_id),
            "metrics": metrics,
            "sonar_project_key": sonar_project_key,
        }
        doc = self.collection.find_one_and_update(
            {"job_id": payload["job_id"]},
            {"$set": payload},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return self._serialize(doc)

    def list_results_paginated(
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
            query["project_id"] = ObjectId(project_id)

        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        items = [self._serialize(doc) for doc in cursor]
        return {"items": items, "total": total}

    def list_results(
        self, project_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if project_id:
            query["project_id"] = ObjectId(project_id)
        cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
        return [self._serialize(doc) for doc in cursor]

    def get_by_job_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        doc = self.collection.find_one({"job_id": ObjectId(job_id)})
        return self._serialize(doc) if doc else None

    def get_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        doc = self.collection.find_one({"_id": ObjectId(result_id)})
        return self._serialize(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"project_id": ObjectId(project_id)})
        return [self._serialize(doc) for doc in cursor]

    def _serialize(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        if not doc:
            return {}
        if "_id" in doc:
            doc["id"] = str(doc.pop("_id"))
        return doc


__all__ = ["ScanResultRepository"]
