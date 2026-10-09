import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.exceptions import InvalidCredentialsError
from app.auth.rate_limiter import (
    clear_successful_login_failures,
    get_lock_ttl,
    get_scope_ids,
    register_failure,
)
from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.users.models import User


# Used when the requested account does not exist.
#
# IMPORTANT:
# Generate this once, not for every request.
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "..."
)


async def authenticate(
    session: AsyncSession,
    redis_client,
    email: str,
    password: str,
    ip: str,
):
    email = email.strip().lower()

    scope_ids = get_scope_ids(
        email=email,
        ip=ip,
    )

    # -----------------------------------------
    # 1. Check all rate-limit scopes.
    # -----------------------------------------

    lock_ttl_ms = await get_lock_ttl(
        redis_client,
        scope_ids,
    )

    if lock_ttl_ms > 0:
        raise InvalidCredentialsError(
            "Too many login attempts."
        )

    # -----------------------------------------
    # 2. Find user.
    # -----------------------------------------

    result = await session.execute(
        select(User).where(
            User.email == email
        )
    )

    user = result.scalar_one_or_none()

    # -----------------------------------------
    # 3. Always perform password verification.
    # -----------------------------------------

    stored_hash = (
        user.password_hash
        if user
        else DUMMY_PASSWORD_HASH
    )

    password_valid = await asyncio.to_thread(
        verify_password,
        stored_hash,
        password,
    )

    # -----------------------------------------
    # 4. Authentication failure.
    # -----------------------------------------

    if user is None or not password_valid:

        await register_failure(
            redis_client,
            scope_ids,
        )

        raise InvalidCredentialsError(
            "Invalid email or password."
        )

    # -----------------------------------------
    # 5. Authentication succeeded.
    # -----------------------------------------

    await clear_successful_login_failures(
        redis_client,
        scope_ids,
    )

    access_token = create_access_token(
        user.id
    )

    refresh_token = create_refresh_token(
        user.id
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }