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
    include=["app.tasks.ingestion", "app.tasks.sonar", "app.tasks.submission"],
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
        "app.tasks.sonar.export_metrics": {"queue": "pipeline.exports"},
        "app.tasks.sonar.run_scan_job": {"queue": "pipeline.scan"},
        "app.tasks.ingestion.ingest_project": {"queue": "pipeline.ingest"},
        "app.tasks.submission.submit_scan": {"queue": "pipeline.ingest"},
    },
)

    Queue("pipeline.ingest"),
    Queue("pipeline.scan", queue_arguments={
        "x-max-priority": 10,
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "pipeline.scan.dlq"
    }),
    Queue("pipeline.exports"),
    Queue("pipeline.scan.dlq"),
)


@celery_app.task(name="healthcheck")
def healthcheck() -> str:
    return "OK"
