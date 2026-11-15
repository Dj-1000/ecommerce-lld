import pytest
from sqlalchemy import select
from app.auth.models import RefreshSession
from app.auth.utils import decode_token, hash_token


@pytest.mark.asyncio
async def test_logout_revokes_session_and_deletes_redis_key(client, logged_in, db, redis_client):
    token = logged_in["refresh_token"]
    sid = decode_token(token)["sid"]
    r = await client.post("/auth/logout", json={"refresh_token": token})
    assert r.status_code == 200, r.text
    assert await redis_client.get(f"auth:session:{sid}") is None
    rows = (await db.scalars(select(RefreshSession).where(RefreshSession.session_id == sid))).all()
    assert rows and all(row.revoked_at is not None for row in rows)


@pytest.mark.asyncio
async def test_logout_rejects_invalid_token(client):
    r = await client.post("/auth/logout", json={"refresh_token": "invalid"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_accepts_expired_but_signed_token(client, logged_in, db):
    from datetime import datetime, timedelta, timezone
    token = logged_in["refresh_token"]
    row = await db.scalar(select(RefreshSession).where(RefreshSession.token_hash == hash_token(token)))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()
    r = await client.post("/auth/logout", json={"refresh_token": token})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_logout_returns_503_if_redis_delete_fails(
    client, logged_in, redis_client, db
):
    token = logged_in["refresh_token"]
    sid = decode_token(token)["sid"]
    redis_client.fail_delete = True

    response = await client.post("/auth/logout", json={"refresh_token": token})
    assert response.status_code == 503

    # The DB revocation is committed before the Redis deletion attempt.
    rows = (
        await db.scalars(
            select(RefreshSession).where(RefreshSession.session_id == sid)
        )
    ).all()
    assert rows
    assert all(row.revoked_at is not None for row in rows)
