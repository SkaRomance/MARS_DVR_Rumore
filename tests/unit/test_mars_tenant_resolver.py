"""Unit tests for TenantResolver.

Uses a dict-backed fake cache and an httpx.MockTransport-backed
MarsApiClient — no Redis, no network.
"""

from __future__ import annotations

import json
import time
import uuid

import httpx
import pytest

from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import MarsAuthError
from src.infrastructure.mars.jwt_validator import MarsJwtClaims
from src.infrastructure.mars.tenant_resolver import TenantResolver

USER_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()
TOKEN = "bearer-xyz"


class FakeCache:
    """Dict-backed async cache matching the AsyncCache protocol."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.gets = 0
        self.sets = 0
        self.deletes = 0

    async def get(self, key: str) -> str | None:
        self.gets += 1
        return self.store.get(key)

    async def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        self.sets += 1
        self.store[key] = value

    async def delete(self, *keys: str) -> None:
        self.deletes += 1
        for k in keys:
            self.store.pop(k, None)


def _me_body(tenant_id: uuid.UUID | None = TENANT_ID, modules=("noise",)) -> dict:
    body = {
        "userId": str(USER_ID),
        "email": "user@example.com",
        "enabledModules": list(modules),
    }
    if tenant_id is not None:
        body["tenantId"] = str(tenant_id)
    return body


def _mars_client(handler) -> MarsApiClient:
    return MarsApiClient(
        base_url="http://mars.test",
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )


def _claims(tenant_id: uuid.UUID | None = None, modules=()) -> MarsJwtClaims:
    return MarsJwtClaims(
        user_id=USER_ID,
        tenant_id=tenant_id,
        email="user@example.com",
        enabled_modules=list(modules),
        issuer="mars-core",
        audience="mars-module-noise",
        expires_at=int(time.time()) + 300,
    )


# ── tests ───────────────────────────────────────────────────────────


async def test_jwt_has_tenant_skips_cache_and_network():
    cache = FakeCache()

    def handler(request):
        raise AssertionError("MARS /me should not be called when JWT carries tenant_id")

    client = _mars_client(handler)
    try:
        resolver = TenantResolver(cache=cache, mars_client=client)
        ctx = await resolver.resolve(_claims(tenant_id=TENANT_ID, modules=["noise"]), TOKEN)
        assert ctx.tenant_id == TENANT_ID
        assert ctx.user_id == USER_ID
        assert ctx.access_token == TOKEN
        assert ctx.enabled_modules == ["noise"]
        assert cache.gets == 0 and cache.sets == 0
    finally:
        await client.close()


async def test_cache_miss_then_mars_call_then_cached():
    cache = FakeCache()
    call_count = {"n": 0}

    def handler(request):
        call_count["n"] += 1
        return httpx.Response(200, json=_me_body(modules=["noise", "vibrations"]))

    client = _mars_client(handler)
    try:
        resolver = TenantResolver(cache=cache, mars_client=client)

        # First call: miss, MARS call, cache set
        ctx1 = await resolver.resolve(_claims(tenant_id=None), TOKEN)
        assert ctx1.tenant_id == TENANT_ID
        assert ctx1.enabled_modules == ["noise", "vibrations"]
        assert call_count["n"] == 1
        assert cache.sets == 1

        # Second call: hit, no MARS call
        ctx2 = await resolver.resolve(_claims(tenant_id=None), TOKEN)
        assert ctx2.tenant_id == TENANT_ID
        assert call_count["n"] == 1
        assert cache.gets == 2  # one on each call
    finally:
        await client.close()


async def test_user_without_tenant_raises():
    cache = FakeCache()

    def handler(request):
        return httpx.Response(200, json=_me_body(tenant_id=None))

    client = _mars_client(handler)
    try:
        resolver = TenantResolver(cache=cache, mars_client=client)
        with pytest.raises(MarsAuthError, match="no tenant"):
            await resolver.resolve(_claims(tenant_id=None), TOKEN)
        # Failed lookups should NOT be cached
        assert cache.sets == 0
    finally:
        await client.close()


async def test_no_cache_layer_works():
    def handler(request):
        return httpx.Response(200, json=_me_body())

    client = _mars_client(handler)
    try:
        resolver = TenantResolver(cache=None, mars_client=client)
        ctx = await resolver.resolve(_claims(tenant_id=None), TOKEN)
        assert ctx.tenant_id == TENANT_ID
    finally:
        await client.close()


async def test_cache_corruption_falls_through_to_mars():
    cache = FakeCache()
    # Poison the cache with invalid JSON
    cache.store[f"mars:tenant:{USER_ID}"] = "{ not json"

    call_count = {"n": 0}

    def handler(request):
        call_count["n"] += 1
        return httpx.Response(200, json=_me_body())

    client = _mars_client(handler)
    try:
        resolver = TenantResolver(cache=cache, mars_client=client)
        ctx = await resolver.resolve(_claims(tenant_id=None), TOKEN)
        assert ctx.tenant_id == TENANT_ID
        assert call_count["n"] == 1  # Fell through to MARS
    finally:
        await client.close()


async def test_cache_get_raises_falls_back_to_mars():
    class BrokenCache(FakeCache):
        async def get(self, key):
            raise RuntimeError("redis down")

    cache = BrokenCache()

    def handler(request):
        return httpx.Response(200, json=_me_body())

    client = _mars_client(handler)
    try:
        resolver = TenantResolver(cache=cache, mars_client=client)
        ctx = await resolver.resolve(_claims(tenant_id=None), TOKEN)
        # Should still succeed — cache failures degrade gracefully
        assert ctx.tenant_id == TENANT_ID
    finally:
        await client.close()


async def test_cache_setex_raises_does_not_fail_request():
    class BrokenCache(FakeCache):
        async def setex(self, key, ttl, value):
            raise RuntimeError("redis full")

    cache = BrokenCache()

    def handler(request):
        return httpx.Response(200, json=_me_body())

    client = _mars_client(handler)
    try:
        resolver = TenantResolver(cache=cache, mars_client=client)
        ctx = await resolver.resolve(_claims(tenant_id=None), TOKEN)
        assert ctx.tenant_id == TENANT_ID  # Write failure swallowed
    finally:
        await client.close()


async def test_invalidate_removes_from_cache():
    cache = FakeCache()
    cache.store[f"mars:tenant:{USER_ID}"] = json.dumps(
        {"tenant_id": str(TENANT_ID), "email": "u@e.com", "enabled_modules": ["noise"]}
    )

    def handler(request):
        raise AssertionError("should not call MARS")

    client = _mars_client(handler)
    try:
        resolver = TenantResolver(cache=cache, mars_client=client)
        await resolver.invalidate(USER_ID)
        assert f"mars:tenant:{USER_ID}" not in cache.store
        assert cache.deletes == 1
    finally:
        await client.close()


async def test_token_expires_at_populated_from_claims():
    def handler(request):
        return httpx.Response(200, json=_me_body())

    client = _mars_client(handler)
    try:
        resolver = TenantResolver(cache=None, mars_client=client)
        exp = int(time.time()) + 600
        claims = MarsJwtClaims(
            user_id=USER_ID,
            tenant_id=TENANT_ID,
            email=None,
            enabled_modules=[],
            expires_at=exp,
        )
        ctx = await resolver.resolve(claims, TOKEN)
        assert ctx.token_expires_at is not None
        assert abs(ctx.token_expires_at.timestamp() - exp) < 2
    finally:
        await client.close()


async def test_cached_tenant_uuid_roundtrip():
    """Ensure cached tenant_id survives JSON str ↔ UUID conversion."""
    cache = FakeCache()

    def handler(request):
        return httpx.Response(200, json=_me_body())

    client = _mars_client(handler)
    try:
        resolver = TenantResolver(cache=cache, mars_client=client)

        # Populate cache via first call
        await resolver.resolve(_claims(tenant_id=None), TOKEN)

        # Verify cache payload is JSON with string UUID
        stored = cache.store[f"mars:tenant:{USER_ID}"]
        parsed = json.loads(stored)
        assert isinstance(parsed["tenant_id"], str)
        assert uuid.UUID(parsed["tenant_id"]) == TENANT_ID

        # Second call reads cache and returns UUID
        ctx = await resolver.resolve(_claims(tenant_id=None), TOKEN)
        assert isinstance(ctx.tenant_id, uuid.UUID)
        assert ctx.tenant_id == TENANT_ID
    finally:
        await client.close()
