import pytest
from sqlalchemy import select
from app.auth.models import RefreshSession
from app.auth.utils import decode_token, hash_token


@pytest.mark.asyncio
async def test_login_persists_refresh_session(client, active_user, db):
    response = await client.post("/auth/login",
        json={"email": active_user.email, "password": "StrongPass123!"})
    assert response.status_code == 200, response.text
    tokens = response.json()["data"]
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["token_type"] == "bearer" and tokens["expires_in"] > 0
    row = await db.scalar(select(RefreshSession).where(RefreshSession.user_id == active_user.id))
    claims = decode_token(tokens["refresh_token"])
    assert row.token_hash == hash_token(tokens["refresh_token"])
    assert row.session_id == claims["sid"]
    assert row.revoked_at is None and row.expires_at is not None


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(client, active_user):
    r = await client.post("/auth/login", json={"email": active_user.email, "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_unknown_email(client):
    r = await client.post("/auth/login", json={"email": "missing@example.com", "password": "whatever"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_unverified_user(client, unverified_user):
    r = await client.post("/auth/login",
        json={"email": unverified_user.email, "password": "StrongPass123!"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_login_rate_limit(client, active_user):
    for _ in range(5):
        r = await client.post("/auth/login",
            json={"email": active_user.email, "password": "incorrect"})
        assert r.status_code == 401
    r = await client.post("/auth/login",
        json={"email": active_user.email, "password": "StrongPass123!"})
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_login_returns_503_and_revokes_db_session_if_redis_set_fails(
    client, active_user, redis_client, db
):
    redis_client.fail_set = True
    response = await client.post(
        "/auth/login",
        json={"email": active_user.email, "password": "StrongPass123!"},
    )
    assert response.status_code == 503

    rows = (
        await db.scalars(
            select(RefreshSession).where(RefreshSession.user_id == active_user.id)
        )
    ).all()
    assert rows
    assert all(row.revoked_at is not None for row in rows)
