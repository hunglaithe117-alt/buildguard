"""Repository for workflow runs (infra layer)."""

from typing import Optional

from bson import ObjectId

from buildguard_common.models.workflow_run import WorkflowRunRaw
from buildguard_common.repositories.base import BaseRepository


class WorkflowRunRepository(BaseRepository[WorkflowRunRaw]):
    def __init__(self, db):
        super().__init__(db, "workflow_runs", WorkflowRunRaw)

    def find_by_repo_and_run_id(
        self, repo_id: str | ObjectId, workflow_run_id: int
    ) -> Optional[WorkflowRunRaw]:
        return self.find_one(
            {"repo_id": self._to_object_id(repo_id), "run_id": workflow_run_id}
        )


__all__ = ["WorkflowRunRepository"]
