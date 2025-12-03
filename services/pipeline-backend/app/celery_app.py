"""Celery application instance for asynchronous work."""

from __future__ import annotations

from celery import Celery, signals
from kombu import Queue

from app.core.config import settings
from app.core.logging import setup_logging


@signals.setup_logging.connect
def on_setup_logging(**kwargs):
    setup_logging(settings.logging.level)


celery_app = Celery(
    "build_commit_pipeline",
    broker=settings.broker.url,
    backend=settings.broker.result_backend,
    include=[
        "app.tasks.sonar",
        "app.tasks.submission",
        "app.tasks.github_ingestion",
        "app.tasks.processing",
        "app.tasks.extractors",
        "app.tasks.extractors",
        "app.tasks.dataset_import",
    ],
)

from buildguard_common.tasks import (
    TASK_IMPORT_REPO,
    TASK_DOWNLOAD_LOGS,
    TASK_PROCESS_WORKFLOW,
    TASK_EXTRACT_BUILD_LOG,
    TASK_EXTRACT_GIT,
    TASK_EXTRACT_REPO_SNAPSHOT,
    TASK_EXTRACT_DISCUSSION,
    TASK_FINALIZE_SAMPLE,
    TASK_SUBMIT_SCAN,
    TASK_RUN_SCAN,
    TASK_EXPORT_METRICS,
)

celery_app.conf.update(
    task_default_queue=settings.broker.default_queue,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_reject_on_worker_lost=True,
    task_retry_backoff=True,
    task_retry_jitter=True,
    task_default_max_retries=2,
    task_routes={
        TASK_EXPORT_METRICS: {"queue": "pipeline.exports"},
        TASK_RUN_SCAN: {"queue": "pipeline.scan"},
        TASK_SUBMIT_SCAN: {"queue": "pipeline.ingest"},
        TASK_IMPORT_REPO: {"queue": "import_repo"},
        TASK_DOWNLOAD_LOGS: {"queue": "collect_workflow_logs"},
        TASK_PROCESS_WORKFLOW: {"queue": "data_processing"},
        TASK_EXTRACT_BUILD_LOG: {"queue": "data_processing"},
        TASK_EXTRACT_GIT: {"queue": "data_processing"},
        TASK_EXTRACT_REPO_SNAPSHOT: {"queue": "data_processing"},
        TASK_EXTRACT_DISCUSSION: {"queue": "data_processing"},
        TASK_FINALIZE_SAMPLE: {"queue": "data_processing"},
    },
    task_queues=(
        Queue("pipeline.ingest"),
        Queue(
            "pipeline.scan",
            queue_arguments={
                "x-max-priority": 10,
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": "pipeline.scan.dlq",
            },
        ),
        Queue("pipeline.exports"),
        Queue("pipeline.scan.dlq"),
        Queue("import_repo"),
        Queue("collect_workflow_logs"),
        Queue("data_processing"),
        Queue("ingestion"),
    ),
)


@celery_app.task(name="healthcheck")
def healthcheck() -> str:
    return "OK"
