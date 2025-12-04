"""Celery task helpers shared across BuildGuard services."""

from __future__ import annotations

import logging
from typing import Any, Callable

from celery import Task
from pymongo.database import Database

logger = logging.getLogger(__name__)

# Task Constants
TASK_IMPORT_REPO = "app.tasks.ingestion.import_repo"
TASK_DOWNLOAD_LOGS = "app.tasks.ingestion.download_job_logs"
TASK_PROCESS_WORKFLOW = "app.tasks.processing.process_workflow_run"
TASK_SUBMIT_SCAN = "app.tasks.submission.submit_scan"
TASK_RUN_SCAN = "app.tasks.sonar.run_scan_job"
TASK_EXPORT_METRICS = "app.tasks.sonar.export_metrics"


class MongoTask(Task):
    """
    Celery Task base class that lazily provides a MongoDB database handle.

    Configure by setting `db_factory` to a callable returning a Database.
    """

    abstract = True
    db_factory: Callable[[], Database] | None = None

    def __init__(self) -> None:
        self._db: Database | None = None

    def after_return(  # pragma: no cover - lifecycle hook
        self, status: str, retval: Any, task_id: str, args: tuple, kwargs: dict, einfo
    ) -> None:
        self._db = None

    @property
    def db(self) -> Database:
        if self._db is None:
            if not self.db_factory:
                raise RuntimeError("MongoTask.db_factory is not configured")
            self._db = self.db_factory()
        return self._db

    def on_failure(  # pragma: no cover - logging only
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo
    ) -> None:
        logger.error("Task %s failed: %s", self.name, exc, exc_info=exc)


__all__ = [
    "MongoTask",
    "TASK_IMPORT_REPO",
    "TASK_DOWNLOAD_LOGS",
    "TASK_PROCESS_WORKFLOW",
    "TASK_SUBMIT_SCAN",
    "TASK_RUN_SCAN",
    "TASK_EXPORT_METRICS",
]
