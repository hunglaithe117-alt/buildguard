"""Repository for failed scans (infra layer)."""

from datetime import datetime, timezone
from typing import List, Optional, Union

from bson import ObjectId

from buildguard_common.models.failed_scan import FailedScan, ScanStatus
from buildguard_common.repositories.base import BaseRepository, CollectionName


class FailedScanRepository(BaseRepository[FailedScan]):
    def __init__(self, db):
        super().__init__(db, CollectionName.FAILED_SCANS, FailedScan)

    def get_by_job_id(self, job_id: Union[str, ObjectId]) -> Optional[FailedScan]:
        return self.find_one({"job_id": self._to_object_id(job_id)})

    def list_by_repo(
        self,
        repo_id: Union[str, ObjectId],
        status: ScanStatus,
        skip: int = 0,
        limit: int = 20,
    ) -> List[FailedScan]:
        return self.find_many(
            {"repo_id": self._to_object_id(repo_id), "status": status},
            sort=[("created_at", -1)],
            skip=skip,
            limit=limit,
        )

    def count_pending_by_repo(self, repo_id: Union[str, ObjectId]) -> int:
        return self.collection.count_documents(
            {"repo_id": self._to_object_id(repo_id), "status": ScanStatus.PENDING}
        )

    def update(
        self, failed_scan_id: Union[str, ObjectId], data: dict
    ) -> Optional[FailedScan]:
        data["updated_at"] = datetime.now(timezone.utc)
        return super().update(failed_scan_id, data)


__all__ = ["FailedScanRepository"]
