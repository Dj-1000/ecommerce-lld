import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from fastapi import Depends, FastAPI
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.dependencies import get_current_user
from app.auth.models import RefreshSession
from app.auth.router import router as auth_router
from app.auth.utils import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.infra.redis import get_redis
from app.users.models import User

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


class RedisWithFailures:
    def __init__(self, client):
        self.client = client
        self.fail_set = self.fail_get = self.fail_delete = False

    async def set(self, *args, **kwargs):
        from redis.exceptions import RedisError
        if self.fail_set:
            raise RedisError("simulated SET failure")
        return await self.client.set(*args, **kwargs)

    async def get(self, *args, **kwargs):
        from redis.exceptions import RedisError
        if self.fail_get:
            raise RedisError("simulated GET failure")
        return await self.client.get(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        from redis.exceptions import RedisError
        if self.fail_delete:
            raise RedisError("simulated DELETE failure")
        return await self.client.delete(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.client, name)


@pytest_asyncio.fixture
async def engine():
    db_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db_engine
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db_engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db(session_factory):
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def redis_client():
    client = FakeRedis(decode_responses=True)
    yield RedisWithFailures(client)
    await client.aclose()


@pytest_asyncio.fixture
async def app(session_factory, redis_client):
    application = FastAPI()
    application.include_router(auth_router)

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    async def override_redis():
        return redis_client

    application.dependency_overrides[get_db] = override_db
    application.dependency_overrides[get_redis] = override_redis

    @application.get("/test/protected")
    async def protected(current_user: User = Depends(get_current_user)):
        return {"user_id": current_user.id, "email": current_user.email}

    yield application
    application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def active_user(db):
    user = User(email="active@example.com", email_verified=True, is_active=True,
                hashed_password=hash_password("StrongPass123!"))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def unverified_user(db):
    user = User(email="unverified@example.com", email_verified=False, is_active=False,
                hashed_password=hash_password("StrongPass123!"))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def logged_in(client, active_user):
    response = await client.post("/auth/login",
        json={"email": active_user.email, "password": "StrongPass123!"})
    assert response.status_code == 200, response.text
    return response.json()["data"]
