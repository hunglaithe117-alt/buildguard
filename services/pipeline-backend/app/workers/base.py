"""Celery base task definitions for workers."""

from pymongo.database import Database

from buildguard_common.tasks import MongoTask
from buildguard_common.mongo import get_database

from app.services.github.exceptions import GithubRateLimitError, GithubRetryableError
from app.core.config import settings


class PipelineTask(MongoTask):
    """
    Base Celery task used across the pipeline.

    Extends the shared MongoTask to reuse connection handling and adds
    GitHub-specific retry behavior.
    """

    abstract = True

    # MongoTask expects db_factory
    @staticmethod
    def db_factory():
        # Adapter for get_database which might need arguments or config
        # buildguard_common.mongo.get_database usually takes uri and db_name
        return get_database(settings.mongo.uri, settings.mongo.db_name)

    autoretry_for = (GithubRateLimitError, GithubRetryableError)
    retry_backoff = True
    retry_backoff_max = 100
    retry_kwargs = {"max_retries": 5}
    default_retry_delay = 20

    @property
    def db(self) -> Database:
        return super().db
