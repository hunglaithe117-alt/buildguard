"""SonarQube/pipeline producer wiring for delegation to the scan pipeline."""

import logging

from celery import Celery

from app.config import settings

logger = logging.getLogger(__name__)

# Celery client used to delegate jobs to the scan-commit pipeline
pipeline_client = Celery(
    "build_risk_producer",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)


class SonarScanProducer:
    """
    Thin wrapper for submitting scan jobs to the external pipeline service.
    """

    def __init__(self):
        self.task_name = "app.tasks.submission.submit_scan"
        self.queue = "pipeline.ingest"

    def trigger_scan(
        self,
        repo_url: str,
        commit_sha: str,
        project_key: str | None = None,
        repo_slug: str | None = None,
    ) -> str:
        """
        Trigger a scan in the build-commit-pipeline service.
        Returns the AsyncResult ID (task ID).
        """
        logger.info("Triggering scan for %s@%s", repo_url, commit_sha)

        result = pipeline_client.send_task(
            self.task_name,
            kwargs={
                "repo_url": repo_url,
                "commit_sha": commit_sha,
                "project_key": project_key,
                "repo_slug": repo_slug,
            },
            queue=self.queue,
        )

        logger.info("Scan task submitted: %s", result.id)
        return result.id


# Singleton instance
sonar_producer = SonarScanProducer()

__all__ = ["sonar_producer", "SonarScanProducer"]
