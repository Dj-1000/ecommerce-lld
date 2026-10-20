import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rate_limiter import LoginRateLimiter
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.users.models import User


INVALID_CREDENTIALS = "Invalid email or password."
LOGIN_TEMPORARILY_BLOCKED = (
    "Too many failed login attempts. Try again later."
)

EMAIL_NOT_VERIFIED = "Please verify your email before logging in."

REGISTRATION_MESSAGE = (
    "Registration successful. Please check your email to activate your account."
)

VERIFICATION_SENT_MESSAGE = (
    "If an eligible account exists, a verification email has been sent."
)

VERIFICATION_SUCCESS_MESSAGE = "Email verified successfully."


def _hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_verification_token() -> str:
    return secrets.token_urlsafe(32)


async def register_user(
    *,
    payload: RegisterRequest,
    db: AsyncSession,
) -> tuple[User, str]:
    email = str(payload.email).strip().lower()
    phone_number = (
        payload.phone_number.strip()
        if payload.phone_number
        else None
    )

    conditions = [User.email == email]

    if phone_number:
        conditions.append(User.phone_number == phone_number)

    existing = await db.scalar(
        select(User.id).where(or_(*conditions)).limit(1)
    )

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or phone number is already registered.",
        )

    raw_token = _create_verification_token()
    token_hash = _hash_verification_token(raw_token)

    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=settings.email_verification_expire_hours
    )

    user = User(
        email=email,
        phone_number=phone_number,
        hashed_password=hash_password(payload.password),
        email_verified=False,
        is_active=False,
        email_verification_token_hash=token_hash,
        email_verification_expires_at=expires_at,
    )

    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or phone number is already registered.",
        )

    return user, raw_token


async def verify_email(
    *,
    token: str,
    db: AsyncSession,
) -> bool:
    token_hash = _hash_verification_token(token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        update(User)
        .where(
            User.email_verification_token_hash == token_hash,
            User.email_verification_expires_at > now,
            User.email_verified.is_(False),
            User.is_active.is_(False),
        )
        .values(
            email_verified=True,
            is_active=True,
            email_verification_token_hash=None,
            email_verification_expires_at=None,
            updated_at=now,
        )
        .returning(User.id)
    )

    user_id = result.scalar_one_or_none()

    if user_id is None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already-used verification token.",
        )

    await db.commit()
    return True


async def create_resend_verification_token(
    *,
    email: str,
    db: AsyncSession,
) -> tuple[str, str] | None:
    normalized_email = email.strip().lower()

    user = await db.scalar(
        select(User).where(
            User.email == normalized_email,
            User.email_verified.is_(False),
            User.is_active.is_(False),
        )
    )

    if user is None:
        return None

    raw_token = _create_verification_token()

    user.email_verification_token_hash = _hash_verification_token(
        raw_token
    )
    user.email_verification_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(hours=settings.email_verification_expire_hours)
    )

    await db.commit()

    return user.email, raw_token


async def login_user(
    *,
    payload: LoginRequest,
    db: AsyncSession,
    redis: Redis,
    ip_address: str,
) -> TokenResponse:
    email = str(payload.email).strip().lower()
    limiter = LoginRateLimiter(redis)

    if await limiter.is_locked(email, ip_address):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=LOGIN_TEMPORARILY_BLOCKED,
            headers={"Retry-After": str(limiter.LOCK_SECONDS)},
        )

    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()

    password_ok = bool(
        user is not None
        and verify_password(
            payload.password,
            getattr(user, "hashed_password", ""),
        )
    )

    if not password_ok:
        await limiter.record_failure(email, ip_address)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    await limiter.clear_pair_failures(email, ip_address)

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=EMAIL_NOT_VERIFIED,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    subject = str(user.id)

    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
        expires_in=settings.access_token_expire_minutes * 60,
    )