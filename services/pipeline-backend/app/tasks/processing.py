import logging
from typing import Any, Dict

from bson import ObjectId
from app.celery_app import celery_app
from app.domain.entities import BuildSample
from app.repositories import (
    BuildSampleRepository,
    ImportedRepositoryRepository,
    WorkflowRunRepository,
)
from app.workers import PipelineOrchestrator, PipelineTask
from buildguard_common.tasks import TASK_PROCESS_WORKFLOW
from app.utils.events import publish_build_update

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name=TASK_PROCESS_WORKFLOW,
    queue="data_processing",
)
def process_workflow_run(
    self: PipelineTask, repo_id: str, workflow_run_id: int, job_id: str = None
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
            dataset_import_job_id=ObjectId(job_id) if job_id else None,
        )
        build_sample = build_sample_repo.insert_one(build_sample)
    elif job_id:
        # Update existing build sample with job_id if not present
        if not build_sample.dataset_import_job_id:
            build_sample_repo.update_one(
                str(build_sample.id), {"dataset_import_job_id": ObjectId(job_id)}
            )

    build_id = str(build_sample.id)
    # Create or get BuildSample
    # For now, let's assume we want to run the pipeline for this build.
    # We need to find the build_sample first.
    build_sample = build_sample_repo.find_by_workflow_run_id(workflow_run_id)

    if not build_sample:
        # Create it if not exists? Or log error?
        # Usually created by ingestion or webhook handler.
        # Let's assume it exists or we create a placeholder.
        logger.warning(
            f"BuildSample not found for run {workflow_run_id}, skipping orchestration"
        )
        return {"status": "skipped", "reason": "build_sample_not_found"}

    orchestrator = PipelineOrchestrator(self.db)
    orchestrator.run(repo_id, workflow_run.head_sha, str(build_sample.id))

    return {"status": "orchestrated", "build_id": str(build_sample.id)}
