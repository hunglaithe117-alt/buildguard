"""Repository for scan jobs (infra layer)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.domain.entities import ScanJob
from app.infra.repositories.base import BaseRepository


class ScanJobRepository(BaseRepository[ScanJob]):
    def __init__(self, db):
        super().__init__(db, "scan_jobs", ScanJob)

    def get(self, job_id: str | ObjectId) -> Optional[ScanJob]:
        return self.find_by_id(job_id)

    def update(self, job_id: str | ObjectId, data: Dict[str, Any]) -> Optional[ScanJob]:
        data["updated_at"] = datetime.now(timezone.utc)
        return super().update(job_id, data)

    def list_by_repo(self, repo_id: str | ObjectId, skip: int = 0, limit: int = 20) -> List[ScanJob]:
        return self.find_many(
            {"repo_id": self._to_object_id(repo_id)},
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    def count_by_repo(self, repo_id: str | ObjectId) -> int:
        return self.collection.count_documents({"repo_id": self._to_object_id(repo_id)})


__all__ = ["ScanJobRepository"]
