import csv
import io
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from bson import ObjectId

from app.celery_app import celery_app
from app.workers import PipelineTask
from buildguard_common.models import (
    DatasetImportJob,
    IngestionStatus,
    IngestionSourceType,
    ImportStatus,
)
from app.repositories import ImportedRepositoryRepository, WorkflowRunRepository
from app.domain.entities import WorkflowRunRaw
from buildguard_common.github_wiring import (
    get_app_github_client,
    get_public_github_client,
)
from app.core.config import settings
from app.core.redis import get_redis
from app.services.github.ingestion_helper import (
    get_github_client,
    ensure_repository_exists,
    process_workflow_run,
)
from buildguard_common.tasks import TASK_DOWNLOAD_LOGS

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="pipeline.tasks.dataset_import.import_dataset",
    queue="ingestion",
)
def import_dataset(self: PipelineTask, job_id: str) -> Dict[str, Any]:
    db = self.db
    import_jobs = db["dataset_import_jobs"]

    # 1. Get Job
    job_doc = import_jobs.find_one({"_id": ObjectId(job_id)})
    if not job_doc:
        logger.error(f"Dataset import job {job_id} not found.")
        return {"status": "failed", "error": "Job not found"}

    job = DatasetImportJob(**job_doc)

    # Update status to PROCESSING
    import_jobs.update_one(
        {"_id": ObjectId(job_id)},
        {
            "$set": {
                "status": IngestionStatus.PROCESSING,
                "started_at": datetime.utcnow(),
            }
        },
    )

    try:
        if job.source_type == IngestionSourceType.GITHUB:
            result = process_github_ingestion(self, job)
        elif job.source_type == IngestionSourceType.CSV:
            result = process_csv_ingestion(self, job)
        else:
            raise ValueError(f"Unsupported source type: {job.source_type}")

        # Update status to COMPLETED
        import_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": IngestionStatus.COMPLETED,
                    "completed_at": datetime.utcnow(),
                    "builds_imported": result.get("builds_imported", 0),
                    # logs_downloaded is no longer relevant here, but we keep the field for compatibility or set to 0
                    "logs_downloaded": 0,
                }
            },
        )
        return result

    except Exception as e:
        logger.error(f"Dataset import job {job_id} failed: {e}", exc_info=True)
        import_jobs.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": IngestionStatus.FAILED,
                    "error_message": str(e),
                    "completed_at": datetime.utcnow(),
                }
            },
        )
        raise e


def process_github_ingestion(
    task: PipelineTask, job: DatasetImportJob
) -> Dict[str, Any]:
    # Extract owner/repo from URL or use it directly if it's already in format
    repo_url = job.repo_url
    if "github.com/" in repo_url:
        full_name = repo_url.split("github.com/")[-1].strip("/")
    else:
        full_name = repo_url

    repo_id = ensure_repository_exists(task.db, job.user_id, full_name)

    # If template is selected, we might want to store it in repo metadata or use it for extraction config
    if job.dataset_template_id:
        # Update repo with template info if needed
        pass

    client_context = get_github_client(task.db, full_name)

    builds_imported = 0

    with client_context as gh:
        # Fetch runs
        runs = gh.paginate_workflow_runs(
            full_name, params={"per_page": 100, "status": "completed"}
        )

        for run in runs:
            if job.max_builds and builds_imported >= job.max_builds:
                break

            # Use shared helper
            # trigger_logs=False is already default or we ensure it is False
            is_new = process_workflow_run(task.db, repo_id, run, trigger_logs=False)

            if is_new:
                builds_imported += 1
                # NO log download triggering here

    return {"builds_imported": builds_imported, "logs_downloaded": 0}


def process_csv_ingestion(task: PipelineTask, job: DatasetImportJob) -> Dict[str, Any]:
    content = job.csv_content
    if not content:
        raise ValueError("No CSV content provided")

    reader = csv.DictReader(io.StringIO(content))

    # Validate headers
    required_headers = {"tr_build_id", "gh_project_name", "git_trigger_commit"}
    if not required_headers.issubset(set(reader.fieldnames or [])):
        raise ValueError(f"CSV missing required headers: {required_headers}")

    builds_imported = 0

    # Cache clients to avoid recreating
    clients = {}

    for row in reader:
        full_name = row["gh_project_name"]
        run_id_str = row["tr_build_id"]
        commit_sha = row["git_trigger_commit"]

        try:
            run_id = int(run_id_str)
        except ValueError:
            logger.warning(f"Invalid run_id {run_id_str}, skipping")
            continue

        repo_id = ensure_repository_exists(task.db, job.user_id, full_name)

        if full_name not in clients:
            clients[full_name] = get_github_client(task.db, full_name)

        client_context = clients[full_name]

        try:
            with client_context as gh:
                # Try to fetch specific run
                try:
                    run = gh.get_workflow_run(full_name, run_id)
                except Exception:
                    logger.warning(
                        f"Could not fetch run {run_id} for {full_name}. Trying by commit {commit_sha}"
                    )
                    runs = gh.list_workflow_runs(
                        full_name, params={"head_sha": commit_sha}
                    )
                    if runs and len(runs) > 0:
                        run = runs[0]
                        run_id = run.get("id")  # Update run_id
                    else:
                        logger.warning(
                            f"Could not find run for commit {commit_sha} in {full_name}"
                        )
                        continue

                # Use shared helper
                is_new = process_workflow_run(task.db, repo_id, run, trigger_logs=False)

                if is_new:
                    builds_imported += 1
                    # NO log download triggering here

        except Exception as e:
            logger.error(f"Error processing row {row}: {e}")
            continue

    return {"builds_imported": builds_imported, "logs_downloaded": 0}


@celery_app.task(
    bind=True,
    base=PipelineTask,
    name="pipeline.tasks.dataset_import.trigger_extraction_for_job",
    queue="ingestion",
)
def trigger_extraction_for_job(self: PipelineTask, job_id: str) -> Dict[str, Any]:
    db = self.db
    import_jobs = db["dataset_import_jobs"]
    build_samples = db["build_samples"]

    job_doc = import_jobs.find_one({"_id": ObjectId(job_id)})
    if not job_doc:
        logger.error(f"Job {job_id} not found")
        return {"status": "failed"}

    job = DatasetImportJob(**job_doc)

    # Find all build samples created by this job (or linked to the repos in this job)
    # Since we don't strictly link build_sample to job_id yet, we might need to rely on
    # finding builds for the repos imported by this user/job.
    # However, for now, let's assume we can find them via repo_id if single repo,
    # or we need to iterate over all repos if bulk.

    # Strategy: Iterate over imported repositories for this user?
    # Or better: The import process should have tagged BuildSamples or we query by repo.

    # For single repo import:
    if job.repo_url:
        # Resolve repo_id
        if "github.com/" in job.repo_url:
            full_name = job.repo_url.split("github.com/")[-1].strip("/")
        else:
            full_name = job.repo_url

        repo = db["imported_repositories"].find_one(
            {"full_name": full_name, "user_id": job.user_id}
        )
        if repo:
            repo_id = repo["_id"]

            # Find all builds for this repo
            cursor = build_samples.find({"repo_id": repo_id})
            count = 0
            for doc in cursor:
                run_id = doc["workflow_run_id"]
                # Trigger log download first (chain start)
                celery_app.send_task(
                    TASK_DOWNLOAD_LOGS, args=[str(repo_id), run_id, job_id]
                )
                count += 1

            return {"status": "triggered", "count": count}

    # For CSV import, we might have multiple repos.
    # This is a bit tricky without a direct link.
    # Ideally, BuildSample should have `job_id` or `import_job_id`.
    # But for now, let's just log a warning if we can't easily find them.

    logger.warning("Could not determine builds to extract for job %s", job_id)
    return {"status": "warning", "message": "No builds found or ambiguous target"}
