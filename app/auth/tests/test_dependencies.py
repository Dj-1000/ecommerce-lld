import pytest
from app.auth.utils import decode_token


@pytest.mark.asyncio
async def test_protected_route_accepts_access_token(client, logged_in, active_user):
    r = await client.get("/test/protected",
        headers={"Authorization": f"Bearer {logged_in['access_token']}"})
    assert r.status_code == 200
    assert r.json()["user_id"] == active_user.id


@pytest.mark.asyncio
async def test_protected_route_rejects_missing_token(client):
    r = await client.get("/test/protected")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_protected_route_rejects_refresh_token(client, logged_in):
    r = await client.get("/test/protected",
        headers={"Authorization": f"Bearer {logged_in['refresh_token']}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_rejects_missing_redis_session(client, logged_in, redis_client):
    sid = decode_token(logged_in["access_token"])["sid"]
    await redis_client.delete(f"auth:session:{sid}")
    r = await client.get("/test/protected",
        headers={"Authorization": f"Bearer {logged_in['access_token']}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_returns_503_if_redis_fails(client, logged_in, redis_client):
    redis_client.fail_get = True
    r = await client.get("/test/protected",
        headers={"Authorization": f"Bearer {logged_in['access_token']}"})
    assert r.status_code == 503
