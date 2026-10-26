# api/services/shared.py
"""
État partagé entre plusieurs instances de l'API (Redis, optionnel via REDIS_URL) :
- verrou du planificateur d'alertes (une seule instance vérifie les trajets) ;
- compteurs de limitation de débit (connexion, copilote).
Sans REDIS_URL, tout reste en mémoire : correct pour une seule instance.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque

REDIS_URL = os.getenv("REDIS_URL")
_redis = None


def redis():
    global _redis
    if REDIS_URL and _redis is None:
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def acquire_lock(name: str, ttl_s: int) -> bool:
    """True si cette instance obtient le verrou (toujours True sans Redis)."""
    r = redis()
    if r is None:
        return True
    return bool(await r.set(f"saferoad:lock:{name}", str(os.getpid()), nx=True, ex=ttl_s))


class RateLimiter:
    """Au plus `limit` événements par `window_s` et par clé (fenêtre glissante en mémoire, fixe sous Redis)."""

    def __init__(self, name: str, limit: int, window_s: float) -> None:
        self.name = name
        self.limit = limit
        self.window = window_s
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        q, now = self.events[key], time.monotonic()
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def _rkey(self, key: str) -> str:
        return f"saferoad:rl:{self.name}:{key}:{int(time.time() // self.window)}"

    async def blocked(self, key: str) -> bool:
        r = redis()
        if r is not None:
            return int(await r.get(self._rkey(key)) or 0) >= self.limit
        return len(self._prune(key)) >= self.limit

    async def hit(self, key: str) -> None:
        r = redis()
        if r is not None:
            k = self._rkey(key)
            await r.incr(k)
            await r.expire(k, int(self.window) + 1)
            return
        self._prune(key).append(time.monotonic())

    async def allow(self, key: str) -> bool:
        """Compte l'événement s'il est autorisé."""
        if await self.blocked(key):
            return False
        await self.hit(key)
        return True

    async def reset(self, key: str) -> None:
        r = redis()
        if r is not None:
            await r.delete(self._rkey(key))
        self.events.pop(key, None)
