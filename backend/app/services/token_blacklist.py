"""Token blacklist service using Redis with in-memory fallback.

Used to revoke refresh tokens on logout and during refresh token rotation.
Keys are kept only until the token's natural expiration.
"""

from __future__ import annotations

import logging
import threading
import time
from functools import lru_cache

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "token:blacklist:"


class TokenBlacklist:
    """Manages revoked JWT identifiers (jti)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # In-memory storage mapping jti -> expiry timestamp (monotonic/epoch)
        self._memory_blacklist: dict[str, float] = {}
        self._redis_client: redis.Redis | None = None
        self._redis_checked = False

    def _get_redis(self) -> redis.Redis | None:
        if not self._redis_checked:
            settings = get_settings()
            try:
                client = redis.from_url(
                    settings.redis_url,
                    socket_connect_timeout=0.2,
                    socket_timeout=0.2,
                    decode_responses=True,
                )
                client.ping()
                self._redis_client = client
            except Exception:
                logger.debug("Redis unavailable for token blacklist, using in-memory store")
                self._redis_client = None
            self._redis_checked = True
        return self._redis_client

    def revoke(self, jti: str, expires_in_seconds: int) -> None:
        """Mark a jti as revoked until expires_in_seconds elapsed."""
        if expires_in_seconds <= 0:
            return

        client = self._get_redis()
        if client is not None:
            try:
                client.setex(f"{_KEY_PREFIX}{jti}", expires_in_seconds, "1")
                return
            except Exception:
                logger.warning("Failed to blacklist token in Redis, falling back to memory")

        with self._lock:
            # Purge expired entries from memory to prevent memory leaks
            now = time.time()
            self._memory_blacklist = {
                k: exp for k, exp in self._memory_blacklist.items() if exp > now
            }
            self._memory_blacklist[jti] = now + expires_in_seconds

    def is_revoked(self, jti: str) -> bool:
        """Check if a jti is in the blacklist."""
        client = self._get_redis()
        if client is not None:
            try:
                return bool(client.exists(f"{_KEY_PREFIX}{jti}"))
            except Exception:
                logger.warning("Failed to check Redis blacklist, checking memory")

        with self._lock:
            now = time.time()
            expiry = self._memory_blacklist.get(jti)
            if expiry is None:
                return False
            if expiry <= now:
                del self._memory_blacklist[jti]
                return False
            return True

    def reset_for_tests(self) -> None:
        """Clear memory blacklist and reset client connection for clean test state."""
        with self._lock:
            self._memory_blacklist.clear()
            self._redis_checked = False
            self._redis_client = None


@lru_cache
def get_token_blacklist() -> TokenBlacklist:
    return TokenBlacklist()
