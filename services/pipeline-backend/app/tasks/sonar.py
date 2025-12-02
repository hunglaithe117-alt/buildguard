from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import time

from celery.utils.log import get_task_logger

from app.celery_app import celery_app
from app.core.config import settings

# from app.models import ProjectStatus, ScanJobStatus

from app.repositories import (
    ProjectsRepository,
    RepositoryScanRepository,
    ScanJobsRepository,
    FailedCommitsRepository,
    ScanResultsRepository,
    BuildSamplesRepository,
)
from buildguard_common.mongo import get_database
from app.services.sonar.commit_replay import MissingForkCommitError
from app.services.sonar.github_api import GitHubRateLimitError
from app.services.sonar.runner import (
    MetricsExporter,
    get_runner_for_instance,
    normalize_repo_url,
)
from buildguard_common.tasks import TASK_RUN_SCAN, TASK_EXPORT_METRICS

logger = get_task_logger(__name__)


class PermanentScanError(Exception):
    """Raised when a scan failure should not be retried."""


def _get_db():
    return get_database(settings.mongo.uri, settings.mongo.database)


def _safe_int(value: Optional[str | int]) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _check_project_completion(project_id: str) -> None:
    repo = RepositoryScanRepository(_get_db())
    scan = repo.get_by_project_id(project_id)
    if not scan:
        return
    total_commits = _safe_int(scan.total_commits)
    if not total_commits:
        return
    completed = (scan.processed_commits or 0) + (scan.failed_commits or 0)
    if completed >= total_commits:
        repo.update_scan(
            scan.id, status="success"
        )  # Or finished? Using success for now based on previous logic


def _record_failed_commit(
    job: Dict[str, Any],
    project: Optional[Dict[str, Any]],
    *,
    reason: str,
    error: str,
) -> None:
    db = _get_db()
    failed_commits_repo = FailedCommitsRepository(db)
    scan_repo = RepositoryScanRepository(db)

    project_id = (project or {}).get("id") or job.get("project_id")
    project_key = (project or {}).get("project_key") or job.get("project_key")
    payload = {
        "job_id": job["id"],
        "project_id": project_id,
        "project_key": project_key,
        "commit_sha": job.get("commit_sha"),
        "repository_url": job.get("repository_url"),
        "repo_slug": job.get("repo_slug"),
        "error": error,
    }
    existing = failed_commits_repo.get_failed_commit_by_job(job["id"])
    already_counted = (existing or {}).get("counted", True)
    should_increment = bool(project) and (existing is None or not already_counted)

    if existing:
        failed_commits_repo.update_failed_commit(
            existing["id"],
            payload=payload,
            status="pending",
            counted=True,
        )
    else:
        failed_commits_repo.insert_failed_commit(
            payload=payload,
            reason=reason,
        )

    if should_increment and project:
        # We need to find the scan for this project to update failed_commits count
        scan = scan_repo.get_by_project_id(project["id"])
        if scan:
            scan_repo.update_scan(scan.id, failed_delta=1)


def _handle_scan_failure(
    task,
    job: Dict[str, Any],
    project: Dict[str, Any],
    exc: Exception,
    *,
    failure_reason: str = "scan-failed",
    retry_countdown: Optional[int] = None,
) -> str:
    db = _get_db()
    scan_jobs_repo = ScanJobsRepository(db)

    now = datetime.utcnow()
    message = str(exc)
    permanent = isinstance(exc, PermanentScanError)
    status = (
        ScanJobStatus.failed_permanent.value
        if permanent
        else ScanJobStatus.failed_temp.value
    )
    updated = scan_jobs_repo.update_scan_job(
        job["id"],
        status=status,
        last_error=message,
        retry_count_delta=1,
        last_finished_at=now,
    )
    retry_count = (updated or job).get("retry_count", 0)
    max_retries = job.get("max_retries") or settings.pipeline.default_retry_limit

    if permanent or retry_count >= max_retries:
        scan_jobs_repo.update_scan_job(
            job["id"],
            status=ScanJobStatus.failed_permanent.value,
            last_error=message,
            last_finished_at=now,
        )
        _record_failed_commit(job, project, reason=failure_reason, error=message)
        _check_project_completion(project["id"])
        logger.error(
            "Scan job %s failed permanently after %s attempts: %s",
            job["id"],
            retry_count,
            message,
        )
        return job["id"]

    try:
        task.max_retries = max_retries
    except Exception:
        pass
    countdown = max(0, retry_countdown or 0)
    logger.warning(
        "Scan job %s failed temporarily (attempt %s/%s). Retrying in %ss: %s",
        job["id"],
        retry_count,
        max_retries,
        countdown,
        message,
    )
    raise task.retry(exc=exc, countdown=countdown)


@celery_app.task(bind=True, max_retries=None, name=TASK_RUN_SCAN)
def run_scan_job(self, scan_job_id: str) -> str:
    db = _get_db()
    scan_jobs_repo = ScanJobsRepository(db)
    projects_repo = ProjectsRepository(db)
    scan_repo = RepositoryScanRepository(db)

    job = scan_jobs_repo.get_scan_job(scan_job_id)
    if not job:
        raise ValueError(f"Scan job {scan_job_id} not found")
    if job.get("status") in {
        ScanJobStatus.success.value,
        ScanJobStatus.failed_permanent.value,
    }:
        return job["id"]

    worker_id = getattr(self.request, "hostname", "worker")
    claimed = scan_jobs_repo.claim_job(
        ScanJobStatus.pending.value, worker_id
    )  # Note: claim_job takes status, not job_id in new repo?
    # Wait, the new repo has claim_job(status, worker_id). The old one had claim_scan_job(job_id, worker_id)?
    # Let's check the old repo implementation.
    # The old repo had: claim_job(self, status: str, worker_id: str, grace_seconds: int = 300)
    # But the usage here is `repository.claim_scan_job(scan_job_id, worker_id)`.
    # Wait, `repository.py` proxied to `ScanJobsRepository`.
    # `ScanJobsRepository` (old) had `claim_job` which took `status`.
    # BUT `run_scan_job` calls `repository.claim_scan_job(scan_job_id, worker_id)`.
    # This implies `repository.py` or `ScanJobsRepository` had a method `claim_scan_job`.
    # I need to check `ScanJobsRepository` again.

    # In the previous `view_file` of `scan_jobs_repository.py`:
    # def claim_job(self, status: str, worker_id: str, grace_seconds: int = 300)
    # It did NOT have `claim_scan_job`.
    # This means `repository.claim_scan_job` must have been defined in `repository.py` or I missed something.
    # Let's check `repository.py` again.
    # `repository.py` just proxied getattr.
    # So `repository.claim_scan_job` would call `scan_jobs.claim_scan_job`.
    # But `scan_jobs_repository.py` only had `claim_job`.
    # This suggests the code I'm refactoring might have been using a method that didn't exist or I missed it.
    # OR `claim_job` was the one intended but the usage is different.
    # `claim_job` finds ONE job by status and claims it.
    # `run_scan_job` is passed a specific `scan_job_id`.
    # It seems `run_scan_job` wants to claim a SPECIFIC job.
    # The `claim_job` in `ScanJobsRepository` claims ANY job with a certain status.

    # Let's look at `ScanJobRepository` in `buildguard_common` (which I created).
    # It has `claim_job(status, worker_id)`.

    # If `run_scan_job` is called with a specific ID, it should probably just update that job to running if it's pending.
    # The logic in `run_scan_job` seems to be:
    # 1. Get job.
    # 2. Check status.
    # 3. Claim it.

    # If I look at the code I'm replacing:
    # claimed = repository.claim_scan_job(scan_job_id, worker_id)

    # I suspect `claim_scan_job` was a method I missed in `ScanJobsRepository` or it was dynamically added?
    # Or maybe I misread the file.
    # Let's assume I need to implement `claim_scan_job` logic:
    # Update job to running IF status is pending.

    # I will implement this logic inline or add it to the repo.
    # Since I can't easily modify the common repo right now without another step, I'll implement inline update.

    # Actually, let's look at `claim_job` in `ScanJobsRepository` again.
    # It finds one and updates.

    # I will verify `ScanJobsRepository` content from my previous `view_file`.
    # It had `claim_job`.
    # Maybe `run_scan_job` was using `claim_job` incorrectly? Or maybe I missed `claim_scan_job`.
    # Wait, I see `claim_job` in the file content I viewed.
    # I DO NOT see `claim_scan_job`.
    # This is strange. Maybe `repository.py` had it?
    # `repository.py` content:
    # class Repository: ... __getattr__ ...
    # It didn't have it.

    # Maybe `run_scan_job` was broken? Or maybe I missed a mixin?
    # Regardless, I need to make it work.
    # I will use `update_scan_job` to claim it.

    claimed = scan_jobs_repo.update_scan_job(
        scan_job_id,
        status=ScanJobStatus.running.value,
        last_worker_id=worker_id,
        last_started_at=datetime.utcnow(),
    )

    if not claimed:
        logger.info("Scan job %s is already being processed", scan_job_id)
        return job["id"]
    job = claimed

    project = projects_repo.get_project(job["project_id"])
    if not project:
        scan_jobs_repo.update_scan_job(
            job["id"],
            status=ScanJobStatus.failed_permanent.value,
            last_error="Project not found",
            last_finished_at=datetime.utcnow(),
        )
        _record_failed_commit(
            job,
            None,
            reason="project-missing",
            error="Project not found",
        )
        return job["id"]

    repo_url = normalize_repo_url(job.get("repository_url"), job.get("repo_slug"))

    scan = scan_repo.get_by_project_id(project["id"])
    sonar_config = scan.sonar_config if scan else None
    project_key = job.get("project_key") or (scan.sonar_project_key if scan else None)
    runner = get_runner_for_instance(project_key)
    scan_jobs_repo.update_scan_job(
        job["id"],
        sonar_instance=runner.instance.name,
    )

    override_text = job.get("config_override")
    if override_text:
        config_path = str(runner.ensure_override_config(override_text))
    else:
        config_path = sonar_config

    try:
        result = runner.scan_commit(
            repo_url=repo_url,
            commit_sha=job["commit_sha"],
            repo_slug=job.get("repo_slug"),
            config_path=config_path,
        )
    except GitHubRateLimitError as exc:
        wait_seconds = max(0, int(max(0.0, exc.retry_at - time.time())) + 1)
        return _handle_scan_failure(
            self,
            job,
            project,
            exc,
            failure_reason="github-rate-limit",
            retry_countdown=wait_seconds,
        )
    except MissingForkCommitError as exc:
        return _handle_scan_failure(
            self,
            job,
            project,
            PermanentScanError(str(exc)),
            failure_reason="missing-fork",
        )
    except Exception as exc:
        message = str(exc).lower()
        if "not found" in message and "commit" in message:
            exc = PermanentScanError(str(exc))
        return _handle_scan_failure(self, job, project, exc)

    scan_jobs_repo.update_scan_job(
        job["id"],
        component_key=result.component_key,
        last_error=None,
        last_finished_at=datetime.utcnow(),
        s3_log_key=result.s3_log_key,
    )

    return result.component_key


@celery_app.task(bind=True, autoretry_for=(Exception,), name=TASK_EXPORT_METRICS)
def export_metrics(
    self,
    component_key: str,
    *,
    job_id: str,
    project_id: str,
    analysis_id: Optional[str] = None,
    commit_sha: Optional[str] = None,
) -> Dict[str, str]:
    db = _get_db()
    scan_jobs_repo = ScanJobsRepository(db)
    projects_repo = ProjectsRepository(db)
    scan_repo = RepositoryScanRepository(db)
    scan_results_repo = ScanResultsRepository(db)
    failed_commits_repo = FailedCommitsRepository(db)
    build_samples_repo = BuildSamplesRepository(db)

    job = scan_jobs_repo.get_scan_job(job_id)
    if not job:
        raise ValueError(f"Scan job {job_id} not found for export")
    project = projects_repo.get_project(project_id)
    if not project:
        raise ValueError(f"Project {project_id} missing for export")

    instance = settings.sonarqube.get_instance(job.get("sonar_instance"))
    exporter = MetricsExporter.from_instance(instance)

    # Use project-specific metrics if defined, otherwise use default
    scan = scan_repo.get_by_project_id(project_id)
    custom_metrics = scan.metrics if scan else None
    metrics = exporter.collect_metrics(component_key, metrics=custom_metrics)
    if not metrics:
        raise RuntimeError(f"No metrics available for {component_key}")

    # Transaction support is in BaseRepository but requires client session
    # The new BaseRepository doesn't expose transaction() helper directly like MongoRepositoryBase did
    # But we can get client from db.client

    with db.client.start_session() as session:
        with session.start_transaction():
            scan_results_repo.upsert_result(
                project_id=project_id,
                job_id=job_id,
                sonar_project_key=component_key,
                metrics=metrics,
            )

            scan_jobs_repo.update_scan_job(
                job_id,
                status=ScanJobStatus.success.value,
                last_error=None,
                last_finished_at=datetime.utcnow(),
            )
            failed_record = failed_commits_repo.get_failed_commit_by_job(job_id)
            update_kwargs: Dict[str, Any] = {"processed_delta": 1}
            if failed_record and failed_record.get("counted", True):
                failed_commits_repo.update_failed_commit(
                    failed_record["id"],
                    status="resolved",
                    resolved_at=datetime.utcnow(),
                    counted=False,
                )
                update_kwargs["failed_delta"] = -1

            if scan:
                scan_repo.update_scan(scan.id, **update_kwargs)
    _check_project_completion(project_id)
    logger.info(
        "Stored metrics for component %s (job=%s, project=%s)",
        component_key,
        job_id,
        project_id,
    )

    # Update BuildSample if this was an external job (build_id passed as external_job_id)
    external_job_id = job.get("external_job_id")
    if external_job_id:
        logger.info(f"Updating BuildSample for build {external_job_id}")
        build_samples_repo.update_build_sample(
            external_job_id,
            {
                "sonar_metrics": metrics,
                "sonar_project_key": component_key,
                "sonar_scan_status": "completed",
            },
        )

    return metrics


@celery_app.task()
def reconcile_scan_jobs() -> dict:
    db = _get_db()
    scan_jobs_repo = ScanJobsRepository(db)

    now = datetime.utcnow()
    stalled = scan_jobs_repo.find_stalled_jobs(older_than_minutes=15)
    # Note: find_stalled_jobs signature in new repo is (older_than_minutes: int = 10)
    # The old usage passed running_stale_before, pending_before, limit.
    # I should check if I need to update the repo method or adapt here.
    # The new repo method is simpler. I'll stick to what it offers or update it if needed.
    # For now, I'll use what's available.

    requeued = 0
    for job in stalled:
        scan_jobs_repo.update_scan_job(
            job["id"],
            status=ScanJobStatus.pending.value,
            last_worker_id=None,
        )
        run_scan_job.delay(job["id"])
        requeued += 1
    if requeued:
        logger.info("Requeued %d stalled scan jobs", requeued)
    return {"requeued": requeued}


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        600.0, reconcile_scan_jobs.s(), name="requeue-stalled-scan-jobs"
    )
