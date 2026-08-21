"""Small fail-open Redis layer for cache and distributed counters."""
import asyncio
import json
from weakref import WeakKeyDictionary

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

_clients: WeakKeyDictionary = WeakKeyDictionary()


def _redis_client() -> Redis:
    """Keep one connection pool per asyncio loop (workers/tests may use several)."""
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None:
        client = Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=0.35,
            socket_timeout=0.35,
        )
        _clients[loop] = client
    return client


async def cache_get(key: str):
    try:
        value = await _redis_client().get(key)
        return json.loads(value) if value else None
    except (RedisError, OSError, RuntimeError, json.JSONDecodeError):
        return None


async def cache_set(key: str, value, ttl: int) -> None:
    try:
        await _redis_client().set(key, json.dumps(value, default=str), ex=ttl)
    except (RedisError, OSError, RuntimeError):
        pass


async def cache_delete(*keys: str) -> None:
    if not keys:
        return
    try:
        await _redis_client().delete(*keys)
    except (RedisError, OSError, RuntimeError):
        pass


async def redis_ready() -> bool:
    try:
        return bool(await _redis_client().ping())
    except (RedisError, OSError, RuntimeError):
        return False


async def rate_limit_hit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Return (allowed, remaining); fail open if Redis is unavailable."""
    try:
        client = _redis_client()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
        return count <= limit, max(0, limit - count)
    except (RedisError, OSError, RuntimeError):
        return True, limit
