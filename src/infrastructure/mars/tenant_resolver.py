"""Tenant resolution for MARS-authenticated requests.

Given a validated JWT + raw bearer token, produce a `MarsContext`
containing the tenant_id, enabled_modules, and token for downstream
MARS calls.

Resolution priority (fastest first):
1. If the JWT itself carries a `tenant_id` claim (future MARS JWTs per
   Wave 24 M5), trust it directly — zero external calls.
2. Otherwise check Redis cache keyed by user_id (TTL 5 min default).
3. On miss, call MARS `/me` to fetch tenant + modules, cache, return.

The cache layer is duck-typed: any object with async `get(key) -> str | None`
and `setex(key, ttl, value) -> None` works. This lets tests inject
a dict-backed fake without touching Redis.

Cache key format: `mars:tenant:{user_id}` — namespaced so multiple
services sharing a Redis DB don't collide.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import MarsAuthError
from src.infrastructure.mars.jwt_validator import MarsJwtClaims
from src.infrastructure.mars.types import MarsContext

logger = logging.getLogger(__name__)


class AsyncCache(Protocol):
    """Minimal async cache interface (subset of redis.asyncio.Redis)."""

    async def get(self, key: str) -> str | None: ...
    async def setex(self, key: str, ttl_seconds: int, value: str) -> Any: ...
    async def delete(self, *keys: str) -> Any: ...


class TenantResolver:
    """Resolves tenant context for MARS-authenticated requests."""

    CACHE_PREFIX = "mars:tenant:"

    def __init__(
        self,
        cache: AsyncCache | None,
        mars_client: MarsApiClient,
        cache_ttl_seconds: int = 300,
    ):
        self._cache = cache
        self._client = mars_client
        self._ttl = cache_ttl_seconds

    async def resolve(
        self,
        claims: MarsJwtClaims,
        access_token: str,
    ) -> MarsContext:
        """Build a MarsContext from JWT claims + cache / MARS `/me`.

        Raises MarsAuthError if the user has no tenant binding.
        """
        token_expires_at = datetime.fromtimestamp(claims.expires_at, UTC) if claims.expires_at else None

        # Fast path: tenant_id already in JWT
        if claims.tenant_id is not None:
            return MarsContext(
                user_id=claims.user_id,
                tenant_id=claims.tenant_id,
                email=claims.email,
                enabled_modules=list(claims.enabled_modules),
                access_token=access_token,
                token_expires_at=token_expires_at,
            )

        # Cache path
        cached = await self._cache_get(claims.user_id)
        if cached is not None:
            return MarsContext(
                user_id=claims.user_id,
                tenant_id=cached["tenant_id"],
                email=claims.email or cached.get("email"),
                enabled_modules=cached.get("enabled_modules", []),
                access_token=access_token,
                token_expires_at=token_expires_at,
            )

        # Network path: ask MARS
        me = await self._client.get_me(access_token)
        if me.tenant_id is None:
            raise MarsAuthError(f"User {claims.user_id} has no tenant binding in MARS")

        context = MarsContext(
            user_id=claims.user_id,
            tenant_id=me.tenant_id,
            email=me.email,
            enabled_modules=me.enabled_modules or list(claims.enabled_modules),
            access_token=access_token,
            token_expires_at=token_expires_at,
        )

        await self._cache_put(
            claims.user_id,
            {
                "tenant_id": str(me.tenant_id),
                "email": me.email,
                "enabled_modules": me.enabled_modules,
            },
        )

        return context

    async def invalidate(self, user_id: uuid.UUID) -> None:
        """Remove a cached tenant mapping (useful on tenant switch)."""
        if self._cache is None:
            return
        try:
            await self._cache.delete(self._cache_key(user_id))
        except Exception as exc:
            logger.warning("Cache invalidate failed for %s: %s", user_id, exc)

    # ── internal cache helpers ─────────────────────────────────────

    def _cache_key(self, user_id: uuid.UUID) -> str:
        return f"{self.CACHE_PREFIX}{user_id}"

    async def _cache_get(self, user_id: uuid.UUID) -> dict | None:
        if self._cache is None:
            return None
        try:
            raw = await self._cache.get(self._cache_key(user_id))
        except Exception as exc:
            logger.warning("Tenant cache get failed: %s", exc)
            return None
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            if "tenant_id" not in data:
                return None
            data["tenant_id"] = uuid.UUID(data["tenant_id"])
            return data
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("Discarding corrupt tenant cache entry: %s", exc)
            return None

    async def _cache_put(self, user_id: uuid.UUID, value: dict) -> None:
        if self._cache is None:
            return
        try:
            await self._cache.setex(
                self._cache_key(user_id),
                self._ttl,
                json.dumps(value),
            )
        except Exception as exc:
            # Cache failures degrade to network roundtrip; do not fail request
            logger.warning("Tenant cache put failed: %s", exc)
