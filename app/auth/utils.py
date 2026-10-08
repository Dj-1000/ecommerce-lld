from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerifyMismatchError,
)

from app.auth.constants import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
)
from app.core.config import settings


password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    password_hash: str,
    password: str,
) -> bool:
    try:
        return password_hasher.verify(
            password_hash,
            password,
        )
    except (
        VerifyMismatchError,
        InvalidHashError,
    ):
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(
            minutes=settings.access_token_expire_minutes
        ),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "type": REFRESH_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(
            days=settings.refresh_token_expire_days
        ),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )