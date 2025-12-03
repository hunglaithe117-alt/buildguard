from __future__ import annotations

from typing import Optional
from celery.utils.log import get_task_logger

from app.celery_app import celery_app
from app.core.config import settings
from app.repositories import ProjectsRepository, ScanJobsRepository
from buildguard_common.mongo import get_database
from app.tasks.sonar import run_scan_job
from app.services.sonar.runner import normalize_repo_url

logger = get_task_logger(__name__)


def _get_db():
    return get_database(settings.mongo.uri, settings.mongo.database)


@celery_app.task(bind=True)
def submit_scan(
    self,
    repo_url: str,
    commit_sha: str,
    project_key: Optional[str] = None,
    repo_slug: Optional[str] = None,
    external_job_id: Optional[str] = None,
) -> dict:
    """
    Handle external scan submission.
    Creates/Updates Project and ScanJob, then triggers scan.
    """
    logger.info(f"Received scan submission for {repo_url}@{commit_sha}")

    # Normalize URL
    repo_url = normalize_repo_url(repo_url, repo_slug)

    # Derive project key if not provided
    if not project_key:
        if repo_slug:
            project_key = repo_slug.replace("/", "_")
        else:
            # Fallback to simple name from URL
            project_key = repo_url.split("/")[-1].replace(".git", "")

    # Find or Create Project
    db = _get_db()
    projects_repo = ProjectsRepository(db)
    scan_jobs_repo = ScanJobsRepository(db)

    # Try to find existing project
    # Note: ProjectsRepository needs a find_by_key method or similar.
    # The previous code used `repository.find_project_by_key`.
    # Let's check if `ProjectsRepository` has it.
    # If not, I'll use `find_one`.

    project_doc = projects_repo.find_one({"project_key": project_key})
    if not project_doc:
        project_doc = projects_repo.create_project(
            full_name=repo_slug or project_key,
            project_key=project_key,
            total_builds=0,
            total_commits=0,
            source_path="",
        )
    project_id = project_doc["id"]

    # Create Scan Job
    job_doc = scan_jobs_repo.create_scan_job(
        project_id=project_id,
        commit_sha=commit_sha,
        repository_url=repo_url,
        repo_slug=repo_slug,
        project_key=project_key,
        max_retries=settings.pipeline.default_retry_limit,
        external_job_id=external_job_id,
    )

    # Trigger Scan
    run_scan_job.delay(job_doc["id"])

    return {"job_id": job_doc["id"], "project_id": project_id, "status": "queued"}
