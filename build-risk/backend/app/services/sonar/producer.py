import logging
from celery import Celery
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize a Celery client to send tasks to the pipeline
# We use the shared broker URL
pipeline_client = Celery(
    "build_risk_producer",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

class SonarScanProducer:
    def __init__(self):
        self.task_name = "app.tasks.submission.submit_scan"
        self.queue = "pipeline.ingest"

    def trigger_scan(
        self,
        repo_url: str,
        commit_sha: str,
        project_key: str = None,
        repo_slug: str = None,
    ) -> str:
        """
        Trigger a scan in the build-commit-pipeline service.
        Returns the AsyncResult ID (task ID).
        """
        logger.info(f"Triggering scan for {repo_url}@{commit_sha}")
        
        # Send task to the pipeline
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
        
        logger.info(f"Scan task submitted: {result.id}")
        return result.id

# Singleton instance
sonar_producer = SonarScanProducer()
