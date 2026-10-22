from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text

from app.db.session import engine
from app.core.config import settings
from app.auth.router import router as auth_router
from app.users.router import router as user_router
from app.core.exceptions import register_exception_handlers

from app.core.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    app.state.redis = redis

    try:
        await redis.ping()
        yield
    finally:
        await redis.aclose()
        await engine.dispose()


app = FastAPI(
    title="LLD E-commerce API",
    lifespan=lifespan,
)
register_exception_handlers(app)
app.include_router(auth_router)
app.include_router(user_router)


@app.get("/health/db")
async def check_database():
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            value = result.scalar_one()

        return {
            "database": "connected",
            "query_result": value,
        }

    except Exception as exc:
        return {
            "database": "error",
            "detail": str(exc),
        }
    