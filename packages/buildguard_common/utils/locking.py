import logging
from contextlib import contextmanager
from typing import Generator

import redis
from buildguard_common.redis import get_redis

logger = logging.getLogger(__name__)


@contextmanager
def repo_lock(repo_id: str, timeout: int = 300) -> Generator[bool, None, None]:
    """
    Acquires a lock for a specific repository to prevent concurrent git operations.

    Args:
        repo_id: The ID of the repository to lock.
        timeout: Maximum time to wait for the lock in seconds.
    """
    redis_client = get_redis()
    lock_name = f"lock:repo:{repo_id}"
    lock = redis_client.lock(lock_name, timeout=300, blocking_timeout=timeout)

    acquired = False
    try:
        acquired = lock.acquire()
        if not acquired:
            logger.warning(
                f"Could not acquire lock for repo {repo_id} after {timeout}s"
            )
        yield acquired
    finally:
        if acquired:
            try:
                lock.release()
            except redis.exceptions.LockError:
                logger.warning(
                    f"Could not release lock for repo {repo_id} (maybe expired)"
                )
