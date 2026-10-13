from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rate_limiter import LoginRateLimiter
from app.auth.schemas import LoginRequest, TokenResponse
from app.auth.utils import create_access_token, create_refresh_token, verify_password
from app.core.config import settings
from app.users.models import User

INVALID_CREDENTIALS = "Invalid email or password."
LOGIN_TEMPORARILY_BLOCKED = "Too many failed login attempts. Try again later."


async def login_user(
    *, payload: LoginRequest, db: AsyncSession, redis: Redis, ip_address: str
) -> TokenResponse:
    email = str(payload.email).strip().lower()
    limiter = LoginRateLimiter(redis)

    if await limiter.is_locked(email, ip_address):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=LOGIN_TEMPORARILY_BLOCKED,
            headers={"Retry-After": str(limiter.LOCK_SECONDS)},
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    password_ok = bool(
        user is not None
        and verify_password(payload.password, getattr(user, "hashed_password", ""))
    )
    account_active = bool(user is not None and getattr(user, "is_active", True))

    if not password_ok or not account_active:
        await limiter.record_failure(email, ip_address)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    await limiter.clear_pair_failures(email, ip_address)
    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
        expires_in=settings.access_token_expire_minutes * 60,
    )
