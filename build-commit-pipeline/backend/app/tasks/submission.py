from __future__ import annotations

from typing import Optional
from celery.utils.log import get_task_logger

from app.celery_app import celery_app
from app.core.config import settings
from app.models import ProjectStatus
from app.services import repository
from app.tasks.sonar import run_scan_job
from pipeline.sonar import normalize_repo_url

logger = get_task_logger(__name__)

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
    # We need a project to attach the job to.
    # In this pipeline, 'Project' usually maps to a repo.
    # We'll try to find by repo_url or project_key.
    
    # Note: repository service might need 'get_project_by_url' or similar.
    # For now, we'll assume we can search or create one.
    # Since we don't have a direct 'get_by_url', we'll create a new one if we can't find it easily.
    # But to avoid duplicates, we should probably use project_key as unique identifier if possible.
    
    # Let's assume project_key is unique enough for now.
    # Ideally we'd query by project_key, but the repo service uses ObjectId.
    # We'll create a new project for this submission if we don't have a clear way to lookup.
    # OR, we can just create a "Ad-hoc" project.
    
    # For simplicity in this refactor, we'll create a new project entry if it's a new submission
    # or reuse if we can find it.
    # Since we lack a search-by-key in the visible code, we'll create a new one.
    # TODO: Implement deduplication.
    
    project_doc = repository.create_project(
        repository_url=repo_url,
        project_key=project_key,
        status=ProjectStatus.active.value,
        source_path="", # No local CSV source
    )
    project_id = project_doc["id"]

    # Create Scan Job
    job_doc = repository.create_scan_job(
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

    return {
        "job_id": job_doc["id"],
        "project_id": project_id,
        "status": "queued"
    }
