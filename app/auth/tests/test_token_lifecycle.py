import pytest


@pytest.mark.asyncio
async def test_access_token_invalid_after_logout(client, logged_in):
    r = await client.post("/auth/logout", json={"refresh_token": logged_in["refresh_token"]})
    assert r.status_code == 200
    r = await client.get("/test/protected",
        headers={"Authorization": f"Bearer {logged_in['access_token']}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_new_access_token_works_after_refresh(client, logged_in):
    r = await client.post("/auth/refresh", json={"refresh_token": logged_in["refresh_token"]})
    assert r.status_code == 200
    access = r.json()["data"]["access_token"]
    r = await client.get("/test/protected", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_inactive_user_rejected(client, logged_in, active_user, db):
    active_user.is_active = False
    await db.commit()
    r = await client.get("/test/protected",
        headers={"Authorization": f"Bearer {logged_in['access_token']}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_unverified_user_rejected(client, logged_in, active_user, db):
    active_user.email_verified = False
    await db.commit()
    r = await client.get("/test/protected",
        headers={"Authorization": f"Bearer {logged_in['access_token']}"})
    assert r.status_code == 401
