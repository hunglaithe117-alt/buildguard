import logging
from datetime import datetime
from bson import ObjectId

from app.celery_app import celery_app

from app.database.mongo import get_db
from app.infra.repositories import (
    ScanJobRepository,
    ScanResultRepository,
    FailedScanRepository,
    ImportedRepositoryRepository,
)
from app.domain.entities import ScanJobStatus  # type: ignore
from app.domain.entities import FailedScan, ScanErrorType, ScanStatus
from app.config import settings

logger = logging.getLogger(__name__)


from app.services.sonar.producer import sonar_producer

@celery_app.task(bind=True, name="app.tasks.sonar.run_sonar_scan")
def run_sonar_scan(self, job_id: str):
    logger.info(f"Delegating SonarQube scan job {job_id} to pipeline")

    db = next(get_db())
    job_repo = ScanJobRepository(db)
    repo_repo = ImportedRepositoryRepository(db)

    job = job_repo.get(job_id)
    if not job:
        logger.error(f"ScanJob {job_id} not found")
        return

    try:
        repo_doc = repo_repo.get(str(job.repo_id))
        if not repo_doc:
            raise ValueError("Repository not found")

        repo_url = repo_doc.html_url
        if not repo_url:
            raise ValueError("Repository URL not found")

        # Trigger scan in pipeline
        # We use the repo name as the project key suffix to match previous logic if possible,
        # or let the pipeline derive it.
        # Previous logic: project_key = f"{settings.SONAR_DEFAULT_PROJECT_KEY}_{repo_doc.name}"
        # Pipeline logic: repo_slug.replace("/", "_")
        
        # We'll pass the repo_slug if we have it (repo_doc.full_name?)
        # Assuming repo_doc.name is the slug or name.
        
        pipeline_task_id = sonar_producer.trigger_scan(
            repo_url=repo_url,
            commit_sha=job.commit_sha,
            repo_slug=repo_doc.name, # Assuming name is slug-like or sufficient
        )

        # Update status to RUNNING (or QUEUED_IN_PIPELINE)
        job_repo.update(
            job_id,
            {
                "status": ScanJobStatus.RUNNING,
                "started_at": datetime.utcnow(),
                "worker_id": self.request.id,
                "external_task_id": pipeline_task_id, 
                "logs": f"Delegated to pipeline task: {pipeline_task_id}"
            },
        )
        
        logger.info(f"Delegated job {job_id} to pipeline task {pipeline_task_id}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to delegate scan job {job_id}: {error_msg}")
        job_repo.update(
            job_id,
            {
                "status": ScanJobStatus.FAILED,
                "finished_at": datetime.utcnow(),
                "error_message": error_msg,
            },
        )
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="app.tasks.sonar.process_scan_results")
def process_scan_results(self, job_id: str, metrics: dict, component_key: str):
    logger.info(f"Received scan results for job {job_id} from pipeline")

    db = next(get_db())
    job_repo = ScanJobRepository(db)
    scan_result_repo = ScanResultRepository(db)
    failed_scan_repo = FailedScanRepository(db)
    build_collection = db["build_samples"]

    job = job_repo.get(job_id)
    if not job:
        logger.error(f"ScanJob {job_id} not found")
        return

    try:
        # Store ScanResult
        scan_result_repo.upsert_by_job(
            job_id,
            {
                "repo_id": job.repo_id,
                "job_id": job.id,
                "sonar_project_key": component_key,
                "metrics": metrics,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )

        # Update BuildSample
        build_collection.update_one(
            {"_id": job.build_id},
            {
                "$set": {
                    "sonar_metrics": metrics,
                    "sonar_project_key": component_key,
                    "sonar_scan_status": "completed",
                }
            },
        )

        # Update ScanJob
        job_repo.update(
            job_id,
            {
                "status": ScanJobStatus.SUCCESS,
                "finished_at": datetime.utcnow(),
                "sonar_component_key": component_key,
            },
        )

        # Resolve FailedScan if exists
        failed_scan = failed_scan_repo.get_by_job_id(job_id)
        if failed_scan:
            failed_scan_repo.update(
                str(failed_scan.id),
                {"status": ScanStatus.RESOLVED, "resolved_at": datetime.utcnow()},
            )

        logger.info(f"Successfully processed results for {component_key}")
        return {"status": "success", "metrics_count": len(metrics)}

    except Exception as e:
        logger.error(f"Failed to process results for {component_key}: {e}")
        job_repo.update(
            job_id,
            {
                "status": ScanJobStatus.FAILED,
                "finished_at": datetime.utcnow(),
                "error_message": f"Result processing failed: {str(e)}",
            },
        )
        raise
