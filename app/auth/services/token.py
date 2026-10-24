import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshSession
from app.auth.schemas import TokenResponse
from app.auth.utils import create_access_token, create_refresh_token, decode_token, hash_token
from app.core.config import settings
from app.users.models import User

from app.core.logger import logger

SESSION_KEY_PREFIX = "auth:session:"


def _session_key(session_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_id}"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)


async def issue_token_pair(*, user: User, db: AsyncSession, redis: Redis) -> TokenResponse:
    session_id = str(uuid4())
    refresh_token = create_refresh_token(user.id, session_id)
    token_hash = hash_token(refresh_token)
    expires_at = _refresh_expiry()

    db.add(RefreshSession(session_id=session_id, user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()

    try:
        await redis.set(_session_key(session_id), str(user.id), ex=settings.refresh_token_expire_days * 86400)
    except RedisError as exc:
        await db.execute(
            update(RefreshSession)
            .where(RefreshSession.session_id == session_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.commit()

        logger.exception(f"Failed to create Redis session {session_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        ) from exc

    return TokenResponse(
        access_token=create_access_token(user.id, session_id),
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def refresh_token_pair(*, refresh_token: str, db: AsyncSession, redis: Redis) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
    except jwt.InvalidTokenError:
        raise _unauthorized() from None

    if payload.get("type") != "refresh":
        raise _unauthorized()

    try:
        user_id = int(payload["sub"])
        session_id = str(payload["sid"])
    except (KeyError, TypeError, ValueError):
        raise _unauthorized() from None

    token_hash = hash_token(refresh_token)

    result = await db.execute(select(RefreshSession).where(RefreshSession.token_hash == token_hash).with_for_update())
    old_session = result.scalar_one_or_none()

    if old_session is None or old_session.session_id != session_id:
        raise _unauthorized()

    now = datetime.now(timezone.utc)

    if old_session.revoked_at is not None:
        await db.execute(
            update(RefreshSession)
            .where(RefreshSession.session_id == session_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.commit()

        await redis.delete(_session_key(session_id))
        logger.warning(f"Detected reuse of revoked refresh token for session {session_id}")
        raise _unauthorized()

    expires_at = old_session.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now:
        raise _unauthorized()

    redis_user_id = await redis.get(_session_key(session_id))

    if redis_user_id != str(user_id):
        raise _unauthorized()

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active or not user.email_verified:
        raise _unauthorized()

    new_refresh_token = create_refresh_token(user.id, session_id)
    new_token_hash = hash_token(new_refresh_token)
    new_expires_at = _refresh_expiry()

    old_session.revoked_at = now
    old_session.replaced_by_token_hash = new_token_hash

    db.add(RefreshSession(session_id=session_id, user_id=user.id, token_hash=new_token_hash, expires_at=new_expires_at))
    await db.commit()

    try:
        await redis.set(_session_key(session_id), str(user.id), ex=settings.refresh_token_expire_days * 86400)
    except RedisError as exc:
        await db.execute(
            update(RefreshSession)
            .where(RefreshSession.session_id == session_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.commit()
        await redis.delete(_session_key(session_id))

        logger.exception(f"Failed to renew Redis session {session_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        ) from exc

    return TokenResponse(
        access_token=create_access_token(user.id, session_id),
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def logout_session(*, refresh_token: str, db: AsyncSession, redis: Redis) -> None:
    try:
        payload = decode_token(refresh_token, verify_exp=False)
    except jwt.InvalidTokenError:
        raise _unauthorized() from None

    if payload.get("type") != "refresh":
        raise _unauthorized()

    session_id = payload.get("sid")

    if not isinstance(session_id, str) or not session_id:
        raise _unauthorized()

    token_hash = hash_token(refresh_token)

    result = await db.execute(
        select(RefreshSession).where(RefreshSession.token_hash == token_hash, RefreshSession.session_id == session_id)
    )
    refresh_session = result.scalar_one_or_none()

    if refresh_session is None:
        raise _unauthorized()

    await db.execute(
        update(RefreshSession)
        .where(RefreshSession.session_id == session_id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()

    try:
        await redis.delete(_session_key(session_id))
    except RedisError as exc:
        logger.exception(f"Failed to delete Redis session {session_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session revocation could not be completed.",
        ) from exc

    logger.info(f"Session {session_id} logged out")