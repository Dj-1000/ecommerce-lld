from fastapi import APIRouter

from app.db.session import get_db

router = APIRouter()



    

@router.post("/login")
async def login(
    body: LoginIn,
    request: Request,
    redis_client: redis.Redis = Depends(get_redis),
):
    email = body.username.strip().lower()
    ip = client_ip(request)
    scope_ids = get_scope_ids(email=email, ip=ip)

    # 1. Check whether any scope is currently locked.
    lock_ttl_ms = await get_lock_ttl(redis_client, scope_ids)

    if lock_ttl_ms > 0:
        retry_after = (lock_ttl_ms + 999) // 1000

        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # 2. Find user.
    user = await get_user_by_email(email)

    # 3. Always perform password verification.
    #    Use a dummy Argon2 hash when the account doesn't exist
    #    to reduce timing differences.
    stored_hash = user.password_hash if user else DUMMY_HASH

    password_valid = await asyncio.to_thread(
        verify_password,
        stored_hash,
        body.password,
    )

    # 4. Authentication failed.
    if not user or not password_valid:
        await register_failure(redis_client, scope_ids)

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )

    # 5. Successful authentication.
    await clear_successful_login_failures(redis_client, scope_ids)

    # Later:
    # access_token = create_access_token(user)
    # refresh_token = create_refresh_token(user)

    return {
        "access_token": "...",
        "token_type": "bearer",
    }

@router.post("/refresh")
async def refresh():
    ...


@router.post("/logout")
async def logout():
    ...