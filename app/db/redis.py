from redis.asyncio import from_url, Redis
from app.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = await from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
