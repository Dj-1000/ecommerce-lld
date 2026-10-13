import hashlib
import time
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class LimitPolicy:
    max_attempts: int
    window_seconds: int


class LoginRateLimiter:
    ACCOUNT_POLICY = LimitPolicy(5, 300)
    IP_POLICY = LimitPolicy(5, 300)
    PAIR_POLICY = LimitPolicy(5, 120)
    LOCK_SECONDS = 600
    PREFIX = "auth:login"

    def __init__(self, redis: Redis):
        self.redis = redis

    @staticmethod
    def _safe_part(value: str) -> str:
        return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()

    def _keys(self, email: str, ip_address: str) -> dict[str, str]:
        e = self._safe_part(email)
        ip = self._safe_part(ip_address)
        return {
            "account": f"{self.PREFIX}:fail:account:{e}",
            "ip": f"{self.PREFIX}:fail:ip:{ip}",
            "pair": f"{self.PREFIX}:fail:pair:{e}:{ip}",
            "lock_account": f"{self.PREFIX}:lock:account:{e}",
            "lock_ip": f"{self.PREFIX}:lock:ip:{ip}",
            "lock_pair": f"{self.PREFIX}:lock:pair:{e}:{ip}",
        }

    async def is_locked(self, email: str, ip_address: str) -> bool:
        k = self._keys(email, ip_address)
        return bool(await self.redis.exists(k["lock_account"], k["lock_ip"], k["lock_pair"]))

    async def record_failure(self, email: str, ip_address: str) -> bool:
        k = self._keys(email, ip_address)
        now = time.time()
        policies = {
            "account": self.ACCOUNT_POLICY, "ip": self.IP_POLICY, "pair": self.PAIR_POLICY
        }
        pipe = self.redis.pipeline(transaction=True)
        for scope, policy in policies.items():
            key = k[scope]
            pipe.zremrangebyscore(key, "-inf", now - policy.window_seconds)
            pipe.zadd(key, {f"{now}:{time.time_ns()}": now})
            pipe.expire(key, policy.window_seconds)
            pipe.zcard(key)
        results = await pipe.execute()
        counts = {"account": int(results[3]), "ip": int(results[7]), "pair": int(results[11])}
        locked = any(counts[s] >= policies[s].max_attempts for s in policies)
        if locked:
            lock_pipe = self.redis.pipeline(transaction=True)
            for key in (k["lock_account"], k["lock_ip"], k["lock_pair"]):
                lock_pipe.set(key, "1", ex=self.LOCK_SECONDS)
            await lock_pipe.execute()
        return locked

    async def clear_pair_failures(self, email: str, ip_address: str) -> None:
        # Do not clear account-wide or IP-wide history after one successful login.
        await self.redis.delete(self._keys(email, ip_address)["pair"])
