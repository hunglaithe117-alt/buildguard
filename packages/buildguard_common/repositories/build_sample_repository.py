"""Repository for build samples (infra layer)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from bson import ObjectId

from buildguard_common.models.build_sample import BuildSample
from buildguard_common.repositories.base import BaseRepository


class BuildSampleRepository(BaseRepository[BuildSample]):
    def __init__(self, db):
        super().__init__(db, "build_samples", BuildSample)

    def find_by_repo_and_run_id(
        self, repo_id: str | ObjectId, workflow_run_id: int
    ) -> Optional[BuildSample]:
        return self.find_one(
            {"repo_id": self._to_object_id(repo_id), "workflow_run_id": workflow_run_id}
        )

    # Methods from pipeline-backend
    def update_build_sample(self, build_id: str, updates: Dict[str, Any]) -> None:
        self.collection.update_one({"_id": ObjectId(build_id)}, {"$set": updates})


__all__ = ["BuildSampleRepository"]
