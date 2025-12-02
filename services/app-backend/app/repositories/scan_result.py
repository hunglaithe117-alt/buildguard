"""Repository for scan results (infra layer)."""

from typing import Dict, List

from bson import ObjectId

from app.domain.entities import ScanResult
from buildguard_common.mongo import get_database
from app.repositories.base import BaseRepository


class ScanResultRepository(BaseRepository[ScanResult]):
    def __init__(self, db):
        super().__init__(db, "scan_results", ScanResult)

    def upsert_by_job(self, job_id: str | ObjectId, data: Dict) -> ScanResult:
        filter_query = {"job_id": self._to_object_id(job_id)}
        self.collection.update_one(filter_query, {"$set": data}, upsert=True)
        return self.find_one(filter_query)

    def list_by_repo(
        self, repo_id: str | ObjectId, skip: int = 0, limit: int = 20
    ) -> List[ScanResult]:
        return self.find_many(
            {"repo_id": self._to_object_id(repo_id)},
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    def count_by_repo(self, repo_id: str | ObjectId) -> int:
        return self.collection.count_documents({"repo_id": self._to_object_id(repo_id)})


__all__ = ["ScanResultRepository"]
