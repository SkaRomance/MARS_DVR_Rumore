from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from redis import asyncio as aioredis

from src.bootstrap.config import get_settings


async def init_rate_limiter():
    settings = get_settings()
    redis_connection = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis_connection)


async def close_rate_limiter():
    await FastAPILimiter.close()


auth_limiter = RateLimiter(times=5, seconds=60)
ai_limiter = RateLimiter(times=10, seconds=60)
export_limiter = RateLimiter(times=20, seconds=60)
default_limiter = RateLimiter(times=60, seconds=60)
license_limiter = RateLimiter(times=10, seconds=60)