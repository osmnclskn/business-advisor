
import json
from functools import lru_cache

from redis import Redis

from app.config import get_settings
from app.logging import get_logger

logger = get_logger()


class RedisCache:

    def __init__(self, redis_url: str):
        self._client: Redis | None = None
        self._redis_url = redis_url

    def connect(self) -> bool:
        if self._client is not None:
            return True

        try:
            self._client = Redis.from_url(self._redis_url, decode_responses=True)
            self._client.ping()
            logger.info("Redis connection established")
            return True
        except Exception as conn_error:
            logger.warning(f"Redis connection failed: {conn_error}")
            self._client = None
            return False

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def is_connected(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            return False

    @property
    def client(self) -> Redis | None:
        return self._client

    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def save_session(self, session_id: str, state: dict, ttl_seconds: int = 3600):
        if self._client is None:
            return

        self._client.setex(
            self._session_key(session_id), ttl_seconds, json.dumps(state)
        )

    def get_session(self, session_id: str) -> dict | None:
        if self._client is None:
            return None

        data = self._client.get(self._session_key(session_id))
        if data:
            return json.loads(data)
        return None

    def delete_session(self, session_id: str):
        if self._client is None:
            return

        self._client.delete(self._session_key(session_id))

    def session_exists(self, session_id: str) -> bool:
        if self._client is None:
            return False

        return self._client.exists(self._session_key(session_id)) > 0


@lru_cache(maxsize=1)
def get_redis_cache() -> RedisCache:
    settings = get_settings()
    return RedisCache(settings.redis_url)

