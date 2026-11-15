import pytest
from app.auth.rate_limiter import LoginRateLimiter


@pytest.mark.asyncio
async def test_limiter_locks_at_configured_threshold(redis_client):
    limiter = LoginRateLimiter(redis_client)
    assert not await limiter.is_locked("test@example.com", "127.0.0.1")
    for _ in range(4):
        assert not await limiter.record_failure("test@example.com", "127.0.0.1")
    assert await limiter.record_failure("test@example.com", "127.0.0.1")
    assert await limiter.is_locked("test@example.com", "127.0.0.1")


@pytest.mark.asyncio
async def test_clear_pair_failures_does_not_clear_account_or_ip(redis_client):
    limiter = LoginRateLimiter(redis_client)
    keys = limiter._keys("test@example.com", "127.0.0.1")
    await redis_client.set(keys["account"], "a")
    await redis_client.set(keys["ip"], "i")
    await redis_client.set(keys["pair"], "p")
    await limiter.clear_pair_failures("test@example.com", "127.0.0.1")
    assert await redis_client.get(keys["pair"]) is None
    assert await redis_client.get(keys["account"]) == "a"
    assert await redis_client.get(keys["ip"]) == "i"


@pytest.mark.asyncio
async def test_key_generation_normalizes_email(redis_client):
    limiter = LoginRateLimiter(redis_client)
    assert limiter._keys("TEST@example.com", "127.0.0.1") == limiter._keys(
        " test@example.com ", "127.0.0.1")
