from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, Request


def get_redis(
    request: Request,
) -> redis.Redis:
    return request.app.state.redis


RedisDependency = Annotated[
    redis.Redis,
    Depends(get_redis),
]