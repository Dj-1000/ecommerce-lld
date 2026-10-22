from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_redis
from app.auth.email_service import send_verification_email
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
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
from app.core.responses import SuccessResponse
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _verification_url(token: str) -> str:
    query = urlencode({"token": token})
    return f"{settings.frontend_url.rstrip('/')}/verify-email?{query}"


@router.post(
    "/register",
    response_model=SuccessResponse[dict],
    status_code=201,
)
async def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    user, token = await register_user(
        payload=payload,
        db=db,
    )

    background_tasks.add_task(
        send_verification_email,
        recipient=user.email,
        verification_url=_verification_url(token),
    )

    return SuccessResponse(
        message=REGISTRATION_MESSAGE,
        data={
            "id": user.id,
            "email": user.email,
            "email_verified": user.email_verified,
        },
    )


@router.post(
    "/verify-email",
    response_model=SuccessResponse[dict],
)
async def confirm_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
    await verify_email(
        token=payload.token,
        db=db,
    )

    return SuccessResponse(
        message=VERIFICATION_SUCCESS_MESSAGE,
        data={},
    )


@router.post(
    "/email-verification/resend",
    response_model=SuccessResponse[dict],
)
async def resend_verification(
    payload: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[dict]:
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

    return SuccessResponse(
        message=VERIFICATION_SENT_MESSAGE,
        data={},
    )


@router.post(
    "/login",
    response_model=SuccessResponse[TokenResponse],
)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> SuccessResponse[TokenResponse]:
    ip_address = request.client.host if request.client else "unknown"

    token_response = await login_user(
        payload=payload,
        db=db,
        redis=redis,
        ip_address=ip_address,
    )

    return SuccessResponse(
        message="Login successful.",
        data=token_response,
    )