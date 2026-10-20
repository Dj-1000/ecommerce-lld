from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_redis
from app.auth.email_service import send_verification_email
from app.auth.schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.auth.service import (
    REGISTRATION_MESSAGE,
    VERIFICATION_SENT_MESSAGE,
    VERIFICATION_SUCCESS_MESSAGE,
    create_resend_verification_token,
    login_user,
    register_user,
    verify_email,
)
from app.core.config import settings
from app.db.session import get_db


router = APIRouter(prefix="/auth", tags=["Authentication"])


def _verification_url(token: str) -> str:
    query = urlencode({"token": token})

    return (
        f"{settings.frontend_url.rstrip('/')}"
        f"/verify-email?{query}"
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
)
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    user, token = await register_user(
        payload=payload,
        db=db,
    )

    background_tasks.add_task(
        send_verification_email,
        recipient=user.email,
        verification_url=_verification_url(token),
    )

    return RegisterResponse(message=REGISTRATION_MESSAGE)


@router.post(
    "/verify-email",
    response_model=MessageResponse,
)
async def confirm_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await verify_email(
        token=payload.token,
        db=db,
    )

    return MessageResponse(message=VERIFICATION_SUCCESS_MESSAGE)


@router.post(
    "/email-verification/resend",
    response_model=MessageResponse,
)
async def resend_verification(
    payload: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    result = await create_resend_verification_token(
        email=str(payload.email),
        db=db,
    )

    if result is not None:
        email, token = result

        background_tasks.add_task(
            send_verification_email,
            recipient=email,
            verification_url=_verification_url(token),
        )

    return MessageResponse(message=VERIFICATION_SENT_MESSAGE)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    ip_address = request.client.host if request.client else "unknown"

    return await login_user(
        payload=payload,
        db=db,
        redis=redis,
        ip_address=ip_address,
    )