"""Repository for build samples (infra layer)."""

from typing import Optional

from bson import ObjectId

from app.domain.entities import BuildSample
from app.repositories.base import BaseRepository


class BuildSampleRepository(BaseRepository[BuildSample]):
    def __init__(self, db):
        super().__init__(db, "build_samples", BuildSample)

    def find_by_repo_and_run_id(
        self, repo_id: str | ObjectId, workflow_run_id: int
    ) -> Optional[BuildSample]:
        return self.find_one(
            {"repo_id": self._to_object_id(repo_id), "workflow_run_id": workflow_run_id}
        )


__all__ = ["BuildSampleRepository"]
