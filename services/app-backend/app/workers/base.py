"""Celery base task definitions for workers."""

from pymongo.database import Database

from buildguard_common.tasks import MongoTask

from app.database.mongo import get_database
from app.services.github.exceptions import GithubRateLimitError, GithubRetryableError


class PipelineTask(MongoTask):
    """
    Base Celery task used across the pipeline.

    Extends the shared MongoTask to reuse connection handling and adds
    GitHub-specific retry behavior.
    """

    abstract = True
    db_factory = staticmethod(get_database)
    autoretry_for = (GithubRateLimitError, GithubRetryableError)
    retry_backoff = True
    retry_backoff_max = 100
    retry_kwargs = {"max_retries": 5}
    default_retry_delay = 20

    @property
    def db(self) -> Database:
        return super().db
