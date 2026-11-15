from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from app.auth.models import RefreshSession
from app.auth.utils import hash_token, decode_token


@pytest.mark.asyncio
async def test_refresh_rotates_and_revokes_old_token(client, logged_in, db):
    old = logged_in["refresh_token"]
    r = await client.post("/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200, r.text
    new = r.json()["data"]["refresh_token"]
    assert new != old
    old_row = await db.scalar(select(RefreshSession).where(RefreshSession.token_hash == hash_token(old)))
    new_row = await db.scalar(select(RefreshSession).where(RefreshSession.token_hash == hash_token(new)))
    assert old_row.revoked_at is not None
    assert old_row.replaced_by_token_hash == hash_token(new)
    assert new_row.revoked_at is None
    assert old_row.session_id == new_row.session_id


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(client, logged_in):
    r = await client.post("/auth/refresh", json={"refresh_token": logged_in["access_token"]})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_malformed_token(client):
    r = await client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_expired_db_session(client, logged_in, db):
    token = logged_in["refresh_token"]
    row = await db.scalar(select(RefreshSession).where(RefreshSession.token_hash == hash_token(token)))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()
    r = await client.post("/auth/refresh", json={"refresh_token": token})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_reuse_of_rotated_token_revokes_session(client, logged_in, redis_client, db):
    old = logged_in["refresh_token"]
    first = await client.post("/auth/refresh", json={"refresh_token": old})
    assert first.status_code == 200
    second = await client.post("/auth/refresh", json={"refresh_token": old})
    assert second.status_code == 401
    sid = decode_token(old)["sid"]
    assert await redis_client.get(f"auth:session:{sid}") is None
    rows = (await db.scalars(select(RefreshSession).where(RefreshSession.session_id == sid))).all()
    assert rows and all(row.revoked_at is not None for row in rows)
