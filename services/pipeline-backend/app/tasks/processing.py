import logging
from typing import Any, Dict

from bson import ObjectId
from app.celery_app import celery_app
from app.domain.entities import BuildSample
from app.infra.repositories import (
    BuildSampleRepository,
    ImportedRepositoryRepository,
    WorkflowRunRepository,
)
from app.workers import PipelineTask
from app.workers import PipelineOrchestrator
from app.utils.events import publish_build_update

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="app.tasks.processing.process_workflow_run",
    queue="data_processing",
)
def process_workflow_run(
    self: PipelineTask, repo_id: str, workflow_run_id: int
) -> Dict[str, Any]:
    workflow_run_repo = WorkflowRunRepository(self.db)
    build_sample_repo = BuildSampleRepository(self.db)

    workflow_run = workflow_run_repo.find_by_repo_and_run_id(repo_id, workflow_run_id)
    if not workflow_run:
        logger.error(f"WorkflowRunRaw not found for {repo_id} / {workflow_run_id}")
        return {"status": "error", "message": "WorkflowRunRaw not found"}

    repo_repo = ImportedRepositoryRepository(self.db)
    repo = repo_repo.find_by_id(repo_id)
    if not repo:
        logger.error(f"Repository {repo_id} not found")
        return {"status": "error", "message": "Repository not found"}

    build_sample = build_sample_repo.find_by_repo_and_run_id(repo_id, workflow_run_id)
    if not build_sample:
        build_sample = BuildSample(
            repo_id=ObjectId(repo_id),
            workflow_run_id=workflow_run_id,
            status="pending",
            tr_build_number=workflow_run.run_number,
            tr_original_commit=workflow_run.head_sha,
        )
        build_sample = build_sample_repo.insert_one(build_sample)

    build_id = str(build_sample.id)
    publish_build_update(repo_id, build_id, "in_progress")

    # Delegate to Orchestrator
    PipelineOrchestrator().run_pipeline(build_id)

    return {"status": "processing_started", "build_id": build_id}
