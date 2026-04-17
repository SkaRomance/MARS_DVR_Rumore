import logging

from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate
from redis import asyncio as aioredis

from src.bootstrap.config import get_settings

_redis_connection = None
_redis_available = False
_logger = logging.getLogger(__name__)


async def init_rate_limiter():
    global _redis_connection, _redis_available
    settings = get_settings()
    _redis_connection = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    try:
        await _redis_connection.ping()
        _redis_available = True
    except Exception:
        _redis_connection = None
        _redis_available = False
        _logger.warning("Redis unavailable — rate limiting disabled. All requests will be allowed without rate limits.")


async def close_rate_limiter():
    global _redis_connection, _redis_available
    if _redis_connection:
        await _redis_connection.close()
    _redis_connection = None
    _redis_available = False


def _make_limiter(times: int, seconds: int):
    if not _redis_available:
        return lambda: True

    rate = Rate(times, Duration.SECOND * seconds) if seconds >= 1 else Rate(times, Duration.SECOND)
    limiter = Limiter(rate)
    return RateLimiter(limiter=limiter)


auth_limiter = _make_limiter(5, 60)
ai_limiter = _make_limiter(10, 60)
export_limiter = _make_limiter(20, 60)
default_limiter = _make_limiter(60, 60)
license_limiter = _make_limiter(10, 60)
