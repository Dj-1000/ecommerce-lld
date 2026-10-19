from app.core.config import settings
from app.auth.rate_limiters.memcached import (
    MemcachedRateLimiter,
)
from app.auth.rate_limiters.redis import RedisRateLimiter


async def create_rate_limiter():
    if settings.cache_backend == "redis":
        import redis.asyncio as redis

        client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        await client.ping()
        return RedisRateLimiter(client)

    limiter = MemcachedRateLimiter(
        host=settings.memcached_host,
        port=settings.memcached_port,
    )

    # Verify the local Memcached server is reachable.
    await limiter.is_locked("__startup_check__", "127.0.0.1")
    await limiter.check_connection()
    return limiter