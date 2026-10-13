from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_redis
from app.auth.schemas import LoginRequest, TokenResponse
from app.auth.service import login_user
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    # Only use forwarded headers when a trusted reverse proxy is configured.
    ip_address = request.client.host if request.client else "unknown"
    return await login_user(
        payload=payload, db=db, redis=redis, ip_address=ip_address
    )