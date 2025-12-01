"""Celery task helpers shared across BuildGuard services."""

from __future__ import annotations

import logging
from typing import Any, Callable

from celery import Task
from pymongo.database import Database

logger = logging.getLogger(__name__)


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
