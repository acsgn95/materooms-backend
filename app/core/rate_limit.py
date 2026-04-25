from fastapi import Request, HTTPException, status
from redis.asyncio import Redis


async def rate_limit(request: Request, redis: Redis, limit: int, window: int = 60):
    ip = request.client.host
    path_group = request.url.path.split("/")[3] if len(request.url.path.split("/")) > 3 else "default"
    key = f"rl:{path_group}:{ip}"

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window)

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla istek. Lütfen bekleyin.",
            headers={"Retry-After": str(window)},
        )
