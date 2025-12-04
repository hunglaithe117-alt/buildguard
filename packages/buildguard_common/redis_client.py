from typing import Optional
import redis
from typing import Optional


class RedisClient:
    _client: Optional[redis.Redis] = None

    @classmethod
    def get_client(cls, url: Optional[str] = None) -> redis.Redis:
        if cls._client is None:
            if url is None:
                raise ValueError("Redis URL must be provided for initialization")
            cls._client = redis.from_url(url, decode_responses=True)
        return cls._client


def get_redis(url: Optional[str] = None) -> redis.Redis:
    return RedisClient.get_client(url)
