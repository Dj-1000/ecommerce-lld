# Authentication tests

The tests are located in `app/auth/test/`. Run commands from the repository
root (the directory containing `app/`).

## Install test dependencies

```bash
pip install pytest pytest-asyncio httpx aiosqlite fakeredis
```

Or install `requirements-test.txt` from this bundle:

```bash
pip install -r requirements-test.txt
```

## Redis dependency import

The application should use `app/infra/redis.py` as the canonical module.
Both `app/auth/router.py` and `app/auth/dependencies.py` should import:

```python
from app.infra.redis import get_redis
```

The test fixture overrides this dependency with `fakeredis`; a Redis server is
not needed for the test suite.

## Database

By default, tests use in-memory SQLite and create/drop SQLAlchemy tables for
each test. `aiosqlite` is required.

For PostgreSQL parity, point `TEST_DATABASE_URL` at a **disposable test
database**. The suite creates and drops tables; never use a development or
production database.

PowerShell:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/auth_test"
```

Bash:

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/auth_test"
```

## Run

```bash
python -m pytest app/auth/test -v
```

Run one module:

```bash
python -m pytest app/auth/test/test_login.py -v
python -m pytest app/auth/test/test_refresh.py -v
python -m pytest app/auth/test/test_logout.py -v
python -m pytest app/auth/test/test_dependencies.py -v
python -m pytest app/auth/test/test_token_lifecycle.py -v
python -m pytest app/auth/test/test_rate_limiter.py -v
```

Run selected tests by keyword:

```bash
python -m pytest app/auth/test -k "reuse" -v
```

## Coverage

- Login success and refresh-session persistence.
- Wrong password, unknown email, unverified account, and rate limiting.
- Refresh rotation, old-token revocation, malformed/wrong-type/expired refresh.
- Reuse of a rotated refresh token and session revocation.
- Logout, including an expired-but-validly-signed refresh token.
- Protected-route access, missing/wrong token type, missing Redis session,
  inactive/unverified user, and Redis availability failure.
- Redis rate-limiter threshold, key normalization, and pair-failure clearing.

## Limitations

- SQLite ignores PostgreSQL row-level `SELECT ... FOR UPDATE`. The suite does
  not prove concurrent refresh-token race behavior. Use a disposable PostgreSQL
  test database and add a concurrency test before relying on that behavior.
- These tests do not verify Alembic migration history.
- They are written against the uploaded code and its current response envelope;
  failures may reveal implementation defects or environment differences.
