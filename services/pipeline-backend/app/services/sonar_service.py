import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.repositories import ScanJobsRepository, ProjectsRepository
from app.tasks.sonar import run_scan_job, export_metrics
from app.domain.entities import ScanJobStatus
from pymongo.database import Database

logger = logging.getLogger(__name__)


class SonarService:
    def __init__(self, db: Database):
        self.db = db
        self.scan_job_repo = ScanJobsRepository()
        self.project_repo = ProjectsRepository()

    def scan_and_wait(self, repo_id: str, commit_sha: str) -> Dict[str, Any]:
        """
        Trigger a SonarQube scan and wait for the results.
        This runs synchronously within the worker.
        """
        # 1. Get or Create Project
        project = self.project_repo.find_by_id(repo_id)
        if not project:
            raise ValueError(f"Project {repo_id} not found")

        # 2. Create Scan Job
        scan_job = self.scan_job_repo.create_scan_job(
            project_id=repo_id,
            project_key=project.get("project_key"),
            commit_sha=commit_sha,
            repository_url=project.get("html_url"),  # Assuming html_url is repo_url
            repo_slug=project.get("full_name"),
        )
        job_id = str(scan_job["_id"])

        logger.info(f"Created scan job {job_id} for {repo_id}@{commit_sha}")

        # 3. Run Scan (Synchronously)
        # Note: We call the task function directly, bypassing Celery routing
        try:
            component_key = run_scan_job(job_id)
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            raise

        # 4. Export Metrics (Synchronously)
        # We assume the scan is finished and metrics are ready (or we might need to retry/wait)
        # run_scan_job returns component_key, which implies success of the scanner CLI.
        # However, SonarQube server processing might take a moment.
        # export_metrics handles fetching from SonarQube.

        try:
            metrics = export_metrics(
                component_key=component_key,
                job_id=job_id,
                project_id=repo_id,
                commit_sha=commit_sha,
            )
            return metrics
        except Exception as e:
            logger.error(f"Metrics export failed: {e}")
            raise
