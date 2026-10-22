import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import decode_token
from app.core.redis import get_redis  
from app.db.session import get_db
from app.users.models import User


from app.core.logger import logger

bearer_scheme = HTTPBearer(auto_error=False)
SESSION_KEY_PREFIX = "auth:session:"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload = decode_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise _unauthorized() from None

    if payload.get("type") != "access":
        raise _unauthorized()

    try:
        user_id = int(payload["sub"])
        session_id = str(payload["sid"])
    except (KeyError, TypeError, ValueError):
        raise _unauthorized() from None

    try:
        active_user_id = await redis.get(f"{SESSION_KEY_PREFIX}{session_id}")
    except RedisError as exc:
        logger.exception(f"Redis session validation failed for {session_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        ) from exc

    if isinstance(active_user_id, bytes):
        active_user_id = active_user_id.decode("utf-8")

    if active_user_id != str(user_id):
        raise _unauthorized()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or not user.email_verified:
        raise _unauthorized()

    return user