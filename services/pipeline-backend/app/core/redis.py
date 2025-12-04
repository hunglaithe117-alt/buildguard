import redis
from app.core.config import settings
from buildguard_common.redis_client import get_redis as common_get_redis


def get_redis() -> redis.Redis:
    return common_get_redis(settings.redis.url)
