"""Unit tests for FastAPI MARS dependencies.

Builds a minimal FastAPI app per test, overrides the validator / resolver
deps with stubs, and hits the route via TestClient to verify HTTP
semantics (401 / 402 / 503 etc.).
"""
from __future__ import annotations

import time
import uuid

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.mars import (
    get_mars_client,
    get_mars_jwt_validator,
    get_mars_tenant_resolver,
    require_mars_context,
    require_module_access,
)
from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import (
    MarsApiError,
    MarsAuthError,
    MarsPaymentRequiredError,
)
from src.infrastructure.mars.jwt_validator import MarsJwtClaims
from src.infrastructure.mars.types import MarsContext


USER_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()


# ── stubs ──────────────────────────────────────────────────────────


class StubValidator:
    def __init__(self, claims=None, error=None):
        self._claims = claims
        self._error = error

    async def validate(self, token: str) -> MarsJwtClaims:
        if self._error:
            raise self._error
        return self._claims


class StubResolver:
    def __init__(self, context=None, error=None):
        self._context = context
        self._error = error

    async def resolve(self, claims, token):
        if self._error:
            raise self._error
        return self._context


class StubClient:
    def __init__(self, verify_result=None, verify_error=None):
        self._verify_result = verify_result
        self._verify_error = verify_error

    async def verify_module(self, token, module_key):
        if self._verify_error:
            raise self._verify_error
        return self._verify_result


def _make_app(
    validator=None,
    resolver=None,
    client=None,
    extra_router=None,
):
    app = FastAPI()

    if validator is not None:
        app.dependency_overrides[get_mars_jwt_validator] = lambda: validator
    if resolver is not None:
        app.dependency_overrides[get_mars_tenant_resolver] = lambda: resolver
    if client is not None:
        app.dependency_overrides[get_mars_client] = lambda: client

    @app.get("/protected")
    async def protected(ctx: MarsContext = Depends(require_mars_context)):
        return {
            "user_id": str(ctx.user_id),
            "tenant_id": str(ctx.tenant_id),
            "modules": ctx.enabled_modules,
        }

    if extra_router is not None:
        app.include_router(extra_router)

    return app


def _make_context(modules=("noise",)) -> MarsContext:
    return MarsContext(
        user_id=USER_ID,
        tenant_id=TENANT_ID,
        email="u@e.com",
        enabled_modules=list(modules),
        access_token="bearer-x",
    )


def _make_claims() -> MarsJwtClaims:
    return MarsJwtClaims(
        user_id=USER_ID,
        tenant_id=TENANT_ID,
        email="u@e.com",
        enabled_modules=["noise"],
        issuer="mars-core",
        audience="mars-module-noise",
        expires_at=int(time.time()) + 300,
    )


# ── require_mars_context ───────────────────────────────────────────


def test_missing_auth_header_returns_401():
    app = _make_app(validator=StubValidator(), resolver=StubResolver())
    with TestClient(app) as client:
        r = client.get("/protected")
    assert r.status_code == 401
    assert "Bearer" in r.headers.get("www-authenticate", "")


def test_empty_bearer_returns_401():
    app = _make_app(validator=StubValidator(), resolver=StubResolver())
    with TestClient(app) as client:
        r = client.get("/protected", headers={"Authorization": "Bearer "})
    assert r.status_code == 401


def test_valid_token_returns_context():
    app = _make_app(
        validator=StubValidator(claims=_make_claims()),
        resolver=StubResolver(context=_make_context(modules=["noise"])),
    )
    with TestClient(app) as client:
        r = client.get("/protected", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == str(USER_ID)
    assert body["tenant_id"] == str(TENANT_ID)
    assert body["modules"] == ["noise"]


def test_expired_token_returns_401():
    app = _make_app(
        validator=StubValidator(error=MarsAuthError("Token expired")),
        resolver=StubResolver(),
    )
    with TestClient(app) as client:
        r = client.get("/protected", headers={"Authorization": "Bearer expired"})
    assert r.status_code == 401
    assert "expired" in r.json()["detail"].lower()


def test_user_no_tenant_returns_401():
    app = _make_app(
        validator=StubValidator(claims=_make_claims()),
        resolver=StubResolver(error=MarsAuthError("User has no tenant binding")),
    )
    with TestClient(app) as client:
        r = client.get("/protected", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 401
    assert "tenant" in r.json()["detail"].lower()


def test_mars_upstream_unavailable_returns_503():
    app = _make_app(
        validator=StubValidator(claims=_make_claims()),
        resolver=StubResolver(error=MarsApiError("MARS 500", status_code=500)),
    )
    with TestClient(app) as client:
        r = client.get("/protected", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 503


# ── require_module_access ──────────────────────────────────────────


def test_module_access_enabled_in_jwt_passes():
    # No MARS verify_module needed because module is in JWT
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/noise-feature")
    async def route(ctx: MarsContext = Depends(require_module_access("noise"))):
        return {"ok": True, "tenant": str(ctx.tenant_id)}

    app = _make_app(
        validator=StubValidator(claims=_make_claims()),
        resolver=StubResolver(context=_make_context(modules=["noise"])),
        client=StubClient(),  # verify_module should not be called
        extra_router=router,
    )
    with TestClient(app) as client:
        r = client.get("/noise-feature", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 200


def test_module_access_not_in_jwt_mars_says_enabled_passes():
    from fastapi import APIRouter

    from src.infrastructure.mars.types import MarsModuleVerifyResponse

    router = APIRouter()

    @router.get("/chemical-feature")
    async def route(ctx: MarsContext = Depends(require_module_access("chemical"))):
        return {"ok": True}

    app = _make_app(
        validator=StubValidator(claims=_make_claims()),
        resolver=StubResolver(context=_make_context(modules=["noise"])),
        client=StubClient(
            verify_result=MarsModuleVerifyResponse(enabled=True, moduleKey="chemical")
        ),
        extra_router=router,
    )
    with TestClient(app) as client:
        r = client.get("/chemical-feature", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 200


def test_module_access_payment_required_returns_402():
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/premium-feature")
    async def route(ctx: MarsContext = Depends(require_module_access("premium"))):
        return {"ok": True}

    app = _make_app(
        validator=StubValidator(claims=_make_claims()),
        resolver=StubResolver(context=_make_context(modules=["noise"])),
        client=StubClient(
            verify_error=MarsPaymentRequiredError("not purchased", status_code=402)
        ),
        extra_router=router,
    )
    with TestClient(app) as client:
        r = client.get("/premium-feature", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 402
    assert "premium" in r.json()["detail"].lower()


def test_module_access_mars_says_disabled_returns_402():
    from fastapi import APIRouter

    from src.infrastructure.mars.types import MarsModuleVerifyResponse

    router = APIRouter()

    @router.get("/x-feature")
    async def route(ctx: MarsContext = Depends(require_module_access("x"))):
        return {"ok": True}

    app = _make_app(
        validator=StubValidator(claims=_make_claims()),
        resolver=StubResolver(context=_make_context(modules=["noise"])),
        client=StubClient(
            verify_result=MarsModuleVerifyResponse(
                enabled=False, moduleKey="x", reason="subscription expired"
            )
        ),
        extra_router=router,
    )
    with TestClient(app) as client:
        r = client.get("/x-feature", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 402
    assert "subscription" in r.json()["detail"].lower()


def test_module_access_upstream_failure_returns_503():
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/y-feature")
    async def route(ctx: MarsContext = Depends(require_module_access("y"))):
        return {"ok": True}

    app = _make_app(
        validator=StubValidator(claims=_make_claims()),
        resolver=StubResolver(context=_make_context(modules=["noise"])),
        client=StubClient(
            verify_error=MarsApiError("boom", status_code=500)
        ),
        extra_router=router,
    )
    with TestClient(app) as client:
        r = client.get("/y-feature", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 503


# ── singleton wiring ───────────────────────────────────────────────


def test_singletons_cached_per_app_state(monkeypatch):
    from src.api.dependencies.mars import (
        _cached_jwt_validator,
        _cached_mars_client,
        reset_mars_singletons,
    )
    from src.bootstrap.config import get_settings

    # Point default settings to an HS256 config so the validator factory
    # can build without requiring a real JWKS URL.
    monkeypatch.setenv("MARS_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("MARS_JWT_HS256_SECRET", "x" * 32)
    get_settings.cache_clear()

    reset_mars_singletons()

    # Repeated calls return the same cached instance
    c1 = _cached_mars_client()
    c2 = _cached_mars_client()
    assert c1 is c2

    v1 = _cached_jwt_validator()
    v2 = _cached_jwt_validator()
    assert v1 is v2

    reset_mars_singletons()
    c3 = _cached_mars_client()
    assert c3 is not c1  # reset creates a fresh instance

    # Clean up cached settings so other tests see defaults
    get_settings.cache_clear()
