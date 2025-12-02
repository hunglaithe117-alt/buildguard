import redis
from app.config import settings
from buildguard_common.redis import get_redis as common_get_redis


def get_redis() -> redis.Redis:
    return common_get_redis(settings.REDIS_URL)
