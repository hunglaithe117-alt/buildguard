"""Scan results repository (infra layer)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import ReturnDocument

from app.infra.repositories.base import MongoRepositoryBase


class ScanResultsRepository(MongoRepositoryBase):
    def upsert_result(self, *, job_id: str, project_id: str, metrics: Dict[str, Any], sonar_project_key: str) -> Dict[str, Any]:
        payload = {
            "job_id": ObjectId(job_id),
            "project_id": ObjectId(project_id),
            "metrics": metrics,
            "sonar_project_key": sonar_project_key,
        }
        doc = self.db[self.collections.scan_results_collection].find_one_and_update(
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

        collection = self.db[self.collections.scan_results_collection]
        total = collection.count_documents(query)
        cursor = (
            collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        items = [self._serialize(doc) for doc in cursor]
        return {"items": items, "total": total}

    def list_results(self, project_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if project_id:
            query["project_id"] = ObjectId(project_id)
        cursor = (
            self.db[self.collections.scan_results_collection]
            .find(query)
            .sort("created_at", -1)
            .limit(limit)
        )
        return [self._serialize(doc) for doc in cursor]

    def get_by_job_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db[self.collections.scan_results_collection].find_one(
            {"job_id": ObjectId(job_id)}
        )
        return self._serialize(doc)

    def get_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db[self.collections.scan_results_collection].find_one(
            {"_id": ObjectId(result_id)}
        )
        return self._serialize(doc)

    def list_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        cursor = self.db[self.collections.scan_results_collection].find(
            {"project_id": ObjectId(project_id)}
        )
        return [self._serialize(doc) for doc in cursor]


__all__ = ["ScanResultsRepository"]
