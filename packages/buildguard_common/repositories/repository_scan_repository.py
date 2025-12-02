from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import ReturnDocument

from buildguard_common.models.repository_scan import (
    RepositoryScan,
    ScanCollectionStatus,
)
from buildguard_common.repositories.base import BaseRepository, CollectionName


class RepositoryScanRepository(BaseRepository[RepositoryScan]):
    def __init__(self, db):
        super().__init__(db, CollectionName.REPOSITORY_SCANS, RepositoryScan)

    def create_scan(
        self,
        *,
        project_id: str | ObjectId,
        sonar_project_key: str,
        total_commits: int = 0,
        sonar_config: Optional[str] = None,
    ) -> RepositoryScan:
        now = datetime.utcnow()
        scan = RepositoryScan(
            project_id=project_id,
            sonar_project_key=sonar_project_key,
            total_commits=total_commits,
            sonar_config=sonar_config,
            created_at=now,
            updated_at=now,
        )
        return self.insert_one(scan)

    def get_by_project_id(self, project_id: str | ObjectId) -> Optional[RepositoryScan]:
        return self.find_one({"project_id": self._to_object_id(project_id)})

    def update_scan(
        self,
        scan_id: str | ObjectId,
        *,
        status: Optional[ScanCollectionStatus | str] = None,
        processed_delta: int = 0,
        failed_delta: int = 0,
        last_error: Optional[str] = None,
        sonar_config: Optional[str] = None,
        metrics: Optional[List[str]] = None,
    ) -> Optional[RepositoryScan]:
        updates: Dict[str, Any] = {"updated_at": datetime.utcnow()}

        if status:
            updates["status"] = status
        if last_error is not None:
            updates["last_error"] = last_error
        if sonar_config is not None:
            updates["sonar_config"] = sonar_config
        if metrics is not None:
            updates["metrics"] = metrics

        inc: Dict[str, Any] = {}
        if processed_delta:
            inc["processed_commits"] = processed_delta
        if failed_delta:
            inc["failed_commits"] = failed_delta

        update_doc: Dict[str, Any] = {"$set": updates}
        if inc:
            update_doc["$inc"] = inc

        identifier = self._to_object_id(scan_id)
        if not identifier:
            return None

        result = self.collection.find_one_and_update(
            {"_id": identifier}, update_doc, return_document=ReturnDocument.AFTER
        )
        return self._to_model(result)
