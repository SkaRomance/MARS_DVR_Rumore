# Wave 26 — MARS Integration Backend

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`. Questo wave implementa il client Python che parla con MARS API. Richiede completamento di W24.1-W24.5 (endpoint MARS).

**Goal:** Implementare nel modulo Rumore (Python FastAPI) il layer di integrazione verso MARS: API client con retry, validazione JWT MARS, resolver tenantId con cache Redis, middleware per iniettare contesto MARS nelle routes, DvrSnapshotService per fetch/patch DVR, + refactor delle route esistenti per non usare più le tabelle Company/User/Tenant locali (preparando Migration 016).

**Architecture:** Layer `src/infrastructure/mars/` nuovo. Dipendenze: httpx (già presente), redis (già presente), PyJWT (già presente). Pattern: async client + async cache + FastAPI dependency injection.

**Tech Stack:** httpx, PyJWT, redis asyncio, respx (test mocking).

**Stima:** 3h.

---

## Pre-requisiti

- Wave 25 applicato (o almeno migration 015 per NoiseAssessmentContext)
- MARS W24.1-W24.5 completati (branch noise-module-integration in repo MARS)
- Branch work: `noise-thin-plugin-refactor` (continuiamo su quello di Wave 25)

---

## Task 1: MarsApiClient con httpx

**Files:**
- Create: `src/infrastructure/mars/__init__.py`
- Create: `src/infrastructure/mars/client.py`
- Create: `src/infrastructure/mars/exceptions.py`
- Create: `src/infrastructure/mars/types.py`
- Test: `tests/unit/test_mars_client.py`

- [ ] **Step 1.1: Crea package mars/**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore"
mkdir -p src/infrastructure/mars
touch src/infrastructure/mars/__init__.py
```

- [ ] **Step 1.2: Types + Exceptions**

File: `src/infrastructure/mars/exceptions.py`

```python
"""Exceptions for MARS API client."""


class MarsApiError(Exception):
    """Base exception for MARS API errors."""

    def __init__(self, message: str, status_code: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class MarsAuthError(MarsApiError):
    """401/403 from MARS (invalid/expired token)."""


class MarsNotFoundError(MarsApiError):
    """404 from MARS."""


class MarsConflictError(MarsApiError):
    """409 from MARS (version mismatch, optimistic lock)."""


class MarsPaymentRequiredError(MarsApiError):
    """402 from MARS (module not purchased)."""


class MarsUnavailableError(MarsApiError):
    """5xx from MARS, connection failure, timeout."""
```

File: `src/infrastructure/mars/types.py`

```python
"""Type definitions for MARS API responses."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class MarsMeTenant(BaseModel):
    id: uuid.UUID
    name: str
    role: str


class MarsMeResponse(BaseModel):
    """GET /me response from MARS."""

    user_id: uuid.UUID = Field(alias="userId")
    email: str
    full_name: Optional[str] = Field(None, alias="fullName")
    tenant_id: Optional[uuid.UUID] = Field(None, alias="tenantId")
    tenants: list[MarsMeTenant] = []
    enabled_modules: list[str] = Field(default_factory=list, alias="enabledModules")
    roles_by_company: dict[str, list[str]] = Field(default_factory=dict, alias="rolesByCompany")

    model_config = ConfigDict(populate_by_name=True)


class MarsModuleVerifyResponse(BaseModel):
    enabled: bool
    module_key: str = Field(alias="moduleKey")
    reason: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class MarsDvrCompanyData(BaseModel):
    vat_number: Optional[str] = Field(None, alias="vatNumber")
    legal_name: Optional[str] = Field(None, alias="legalName")
    ateco_code: Optional[str] = Field(None, alias="atecoCode")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MarsDvrWorkPhase(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MarsDvrPhaseEquipment(BaseModel):
    id: str
    phase_id: str = Field(alias="phaseId")
    brand: Optional[str] = None
    model: Optional[str] = None
    tipology: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MarsDvrSnapshot(BaseModel):
    """Full DVR document snapshot (v1.0 or v1.1)."""

    schema_version: Literal["1.0.0", "1.1.0"] = Field(alias="schemaVersion")
    company_data: MarsDvrCompanyData = Field(alias="companyData")
    work_phases: list[MarsDvrWorkPhase] = Field(default_factory=list, alias="workPhases")
    phase_equipments: list[MarsDvrPhaseEquipment] = Field(default_factory=list, alias="phaseEquipments")
    risks: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    trainings: list[dict[str, Any]] = Field(default_factory=list)
    module_extensions: dict[str, dict[str, Any]] = Field(default_factory=dict, alias="module_extensions")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MarsDvrRevisionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID = Field(alias="documentId")
    tenant_id: uuid.UUID = Field(alias="tenantId")
    version: int
    status: str  # draft | published | archived
    snapshot: MarsDvrSnapshot
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class MarsModuleSessionResponse(BaseModel):
    session_id: str = Field(alias="sessionId")
    module_key: str = Field(alias="moduleKey")
    revision_version: int = Field(alias="revisionVersion")
    started_at: datetime = Field(alias="startedAt")

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 1.3: Client httpx**

File: `src/infrastructure/mars/client.py`

```python
"""HTTP client for MARS API with retry and typed responses."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import httpx

from src.infrastructure.mars.exceptions import (
    MarsApiError,
    MarsAuthError,
    MarsConflictError,
    MarsNotFoundError,
    MarsPaymentRequiredError,
    MarsUnavailableError,
)
from src.infrastructure.mars.types import (
    MarsDvrRevisionResponse,
    MarsMeResponse,
    MarsModuleSessionResponse,
    MarsModuleVerifyResponse,
)

logger = logging.getLogger(__name__)


class MarsApiClient:
    """Async HTTP client for MARS API (apps/api NestJS).

    Features:
    - Bearer token authentication
    - Retry on 5xx and connection errors (exponential backoff, max 3)
    - Typed responses via Pydantic
    - Structured error classes
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={"User-Agent": "MARS-DVR-Rumore/0.1"},
        )

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        token: str,
        *,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        url = path  # relative to base_url
        merged_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            merged_headers.update(headers)

        last_exc = None
        for attempt in range(self._max_retries):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    json=json,
                    headers=merged_headers,
                )
                # Retry on 5xx
                if 500 <= response.status_code < 600:
                    if attempt < self._max_retries - 1:
                        backoff = 2**attempt
                        logger.warning(
                            "MARS %s %s returned %d; retrying in %ds",
                            method,
                            path,
                            response.status_code,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue
                return response
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    backoff = 2**attempt
                    logger.warning("MARS %s %s connection error; retry in %ds: %s", method, path, backoff, exc)
                    await asyncio.sleep(backoff)
                    continue
                raise MarsUnavailableError(f"MARS API unreachable after {self._max_retries} attempts: {exc}") from exc

        raise MarsUnavailableError(f"Exhausted retries: {last_exc}")

    def _raise_for_status(self, response: httpx.Response):
        status = response.status_code
        if 200 <= status < 300:
            return

        try:
            payload = response.json()
        except Exception:
            payload = {"message": response.text}

        msg = f"MARS {response.request.method} {response.request.url.path} returned {status}: {payload.get('message', payload)}"

        if status == 401 or status == 403:
            raise MarsAuthError(msg, status_code=status, payload=payload)
        if status == 402:
            raise MarsPaymentRequiredError(msg, status_code=status, payload=payload)
        if status == 404:
            raise MarsNotFoundError(msg, status_code=status, payload=payload)
        if status == 409:
            raise MarsConflictError(msg, status_code=status, payload=payload)
        if 500 <= status < 600:
            raise MarsUnavailableError(msg, status_code=status, payload=payload)

        raise MarsApiError(msg, status_code=status, payload=payload)

    async def get_me(self, token: str) -> MarsMeResponse:
        response = await self._request("GET", "/auth/me", token)
        self._raise_for_status(response)
        return MarsMeResponse.model_validate(response.json())

    async def verify_module(self, token: str, module_key: str) -> MarsModuleVerifyResponse:
        response = await self._request(
            "POST",
            f"/client-app/compliance/modules/verify/{module_key}",
            token,
        )
        # 200 = enabled, 402 = not purchased, 403 = unknown
        if response.status_code == 402:
            return MarsModuleVerifyResponse(enabled=False, moduleKey=module_key, reason="not-purchased")
        if response.status_code == 403:
            return MarsModuleVerifyResponse(enabled=False, moduleKey=module_key, reason="unknown-module")
        self._raise_for_status(response)
        return MarsModuleVerifyResponse.model_validate(response.json())

    async def register_session(
        self,
        token: str,
        module_key: str,
        document_id: uuid.UUID,
        revision_id: uuid.UUID,
    ) -> MarsModuleSessionResponse:
        response = await self._request(
            "POST",
            f"/modules/{module_key}/register-session",
            token,
            json={"documentId": str(document_id), "revisionId": str(revision_id)},
        )
        self._raise_for_status(response)
        return MarsModuleSessionResponse.model_validate(response.json())

    async def heartbeat_session(self, token: str, session_id: str):
        response = await self._request(
            "POST",
            f"/modules/sessions/{session_id}/heartbeat",
            token,
        )
        self._raise_for_status(response)

    async def end_session(self, token: str, session_id: str):
        response = await self._request(
            "POST",
            f"/modules/sessions/{session_id}/end",
            token,
        )
        self._raise_for_status(response)

    async def get_dvr_revision(
        self,
        token: str,
        document_id: uuid.UUID,
        revision_id: uuid.UUID,
    ) -> MarsDvrRevisionResponse:
        response = await self._request(
            "GET",
            f"/dvr-documents/{document_id}/revisions/{revision_id}",
            token,
        )
        self._raise_for_status(response)
        return MarsDvrRevisionResponse.model_validate(response.json())

    async def put_module_extension(
        self,
        token: str,
        document_id: uuid.UUID,
        revision_id: uuid.UUID,
        module_key: str,
        expected_version: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request(
            "PUT",
            f"/dvr-documents/{document_id}/revisions/{revision_id}/module-extensions/{module_key}",
            token,
            json=payload,
            headers={"If-Match": str(expected_version)},
        )
        self._raise_for_status(response)
        return response.json()
```

- [ ] **Step 1.4: Test con respx**

```bash
pip install respx  # o aggiungi a pyproject.toml test deps
```

File: `tests/unit/test_mars_client.py`

```python
"""Unit tests for MarsApiClient using respx for HTTP mocking."""
import pytest
import respx
import httpx
import uuid

from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import (
    MarsAuthError,
    MarsConflictError,
    MarsNotFoundError,
    MarsPaymentRequiredError,
    MarsUnavailableError,
)


@pytest.fixture
async def client():
    async with MarsApiClient(base_url="https://mars.test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_me_success(client):
    with respx.mock:
        respx.get("https://mars.test/auth/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "userId": str(uuid.uuid4()),
                    "email": "a@b.com",
                    "fullName": "Test User",
                    "tenantId": str(uuid.uuid4()),
                    "tenants": [],
                    "enabledModules": ["dvr", "noise"],
                    "rolesByCompany": {},
                },
            )
        )

        me = await client.get_me(token="fake-token")
        assert me.email == "a@b.com"
        assert "noise" in me.enabled_modules


@pytest.mark.asyncio
async def test_get_me_401(client):
    with respx.mock:
        respx.get("https://mars.test/auth/me").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"}),
        )

        with pytest.raises(MarsAuthError):
            await client.get_me(token="bad-token")


@pytest.mark.asyncio
async def test_verify_module_enabled(client):
    with respx.mock:
        respx.post("https://mars.test/client-app/compliance/modules/verify/noise").mock(
            return_value=httpx.Response(200, json={"enabled": True, "moduleKey": "noise"}),
        )

        result = await client.verify_module(token="t", module_key="noise")
        assert result.enabled is True


@pytest.mark.asyncio
async def test_verify_module_payment_required(client):
    with respx.mock:
        respx.post("https://mars.test/client-app/compliance/modules/verify/noise").mock(
            return_value=httpx.Response(402, json={"enabled": False, "reason": "not-purchased"}),
        )

        result = await client.verify_module(token="t", module_key="noise")
        assert result.enabled is False
        assert result.reason == "not-purchased"


@pytest.mark.asyncio
async def test_put_module_extension_conflict(client):
    doc_id, rev_id = uuid.uuid4(), uuid.uuid4()
    with respx.mock:
        respx.put(
            f"https://mars.test/dvr-documents/{doc_id}/revisions/{rev_id}/module-extensions/noise"
        ).mock(
            return_value=httpx.Response(409, json={"message": "Version conflict", "currentVersion": 5, "expectedVersion": 3}),
        )

        with pytest.raises(MarsConflictError) as exc:
            await client.put_module_extension(
                token="t",
                document_id=doc_id,
                revision_id=rev_id,
                module_key="noise",
                expected_version=3,
                payload={"module_version": "0.1.0", "last_sync_at": "2026-04-17T10:00:00Z"},
            )

        assert exc.value.payload["currentVersion"] == 5


@pytest.mark.asyncio
async def test_retries_on_503(client):
    with respx.mock:
        route = respx.get("https://mars.test/auth/me").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(200, json={"userId": str(uuid.uuid4()), "email": "a@b.com", "enabledModules": []}),
            ],
        )

        me = await client.get_me(token="t")
        assert me.email == "a@b.com"
        assert route.call_count == 3


@pytest.mark.asyncio
async def test_gives_up_after_max_retries(client):
    with respx.mock:
        respx.get("https://mars.test/auth/me").mock(
            return_value=httpx.Response(503),
        )

        with pytest.raises(MarsUnavailableError):
            await client.get_me(token="t")
```

- [ ] **Step 1.5: Run test**

```bash
pytest tests/unit/test_mars_client.py -v
```

Expected: 7/7 PASS.

- [ ] **Step 1.6: Commit**

```bash
git add src/infrastructure/mars/ tests/unit/test_mars_client.py pyproject.toml
git commit -m "Wave 26.1: Add MarsApiClient with retry, typed responses, error classes

httpx async client with Bearer auth, exponential backoff retry on 5xx,
typed Pydantic responses, structured MarsApiError hierarchy
(Auth/NotFound/Conflict/PaymentRequired/Unavailable).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: JWT MARS validator

**Scope:** Il modulo Rumore riceve JWT MARS (signed with MARS `JWT_ACCESS_SECRET`). Dobbiamo validarlo senza dover andare in rete a ogni request.

**Strategia:** Shared secret (MARS e Rumore hanno stesso `MARS_JWT_ACCESS_SECRET` in env). Validation locale con PyJWT.

**Files:**
- Create: `src/infrastructure/mars/jwt_validator.py`
- Modify: `src/bootstrap/config.py` (aggiungi `MARS_JWT_ACCESS_SECRET`, `MARS_API_BASE_URL`)
- Test: `tests/unit/test_mars_jwt_validator.py`

- [ ] **Step 2.1: Aggiungi settings MARS**

File: `src/bootstrap/config.py` — aggiungi al `Settings`:

```python
# MARS integration
mars_api_base_url: str = Field(default="http://localhost:5000", alias="MARS_API_BASE_URL")
mars_jwt_access_secret: str = Field(default="replace_me", alias="MARS_JWT_ACCESS_SECRET")
mars_jwt_algorithm: str = Field(default="HS256", alias="MARS_JWT_ALGORITHM")
mars_module_key: str = Field(default="noise", alias="MARS_MODULE_KEY")
mars_events_webhook_secret: str = Field(default="", alias="MARS_EVENTS_WEBHOOK_SECRET")  # for verifying inbound webhooks
```

File: `.env.example` — append:

```bash
# MARS Integration
MARS_API_BASE_URL=http://localhost:5000
MARS_JWT_ACCESS_SECRET=replace_me_same_as_mars
MARS_JWT_ALGORITHM=HS256
MARS_MODULE_KEY=noise
MARS_EVENTS_WEBHOOK_SECRET=
```

- [ ] **Step 2.2: Implementa validator**

File: `src/infrastructure/mars/jwt_validator.py`

```python
"""Validate JWT tokens issued by MARS."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

import jwt

from src.infrastructure.mars.exceptions import MarsAuthError


@dataclass
class MarsJwtClaims:
    """Decoded MARS JWT payload."""

    user_id: uuid.UUID
    email: str
    tenant_id: Optional[uuid.UUID]  # M5: may be absent for multi-tenant users
    token_type: str  # "access" | "refresh"


class MarsJwtValidator:
    def __init__(self, secret: str, algorithm: str = "HS256"):
        self._secret = secret
        self._algorithm = algorithm

    def validate(self, token: str) -> MarsJwtClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["sub", "exp", "type"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise MarsAuthError("Token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise MarsAuthError(f"Invalid token: {exc}") from exc

        if payload.get("type") != "access":
            raise MarsAuthError(f"Expected access token, got {payload.get('type')}")

        try:
            user_id = uuid.UUID(payload["sub"])
        except (ValueError, KeyError) as exc:
            raise MarsAuthError("Invalid sub claim") from exc

        tenant_id = None
        if raw_tenant := payload.get("tenant_id"):
            try:
                tenant_id = uuid.UUID(raw_tenant)
            except ValueError as exc:
                raise MarsAuthError("Invalid tenant_id claim") from exc

        return MarsJwtClaims(
            user_id=user_id,
            email=payload.get("email", ""),
            tenant_id=tenant_id,
            token_type=payload["type"],
        )
```

- [ ] **Step 2.3: Test**

File: `tests/unit/test_mars_jwt_validator.py`

```python
"""Unit tests for MarsJwtValidator."""
import pytest
import jwt
import uuid
import time

from src.infrastructure.mars.jwt_validator import MarsJwtValidator
from src.infrastructure.mars.exceptions import MarsAuthError


SECRET = "test-secret"


def _make_token(payload: dict, secret: str = SECRET, algorithm: str = "HS256") -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


def test_validates_valid_token():
    validator = MarsJwtValidator(SECRET)
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    token = _make_token({
        "sub": str(user_id),
        "email": "a@b.com",
        "tenant_id": str(tenant_id),
        "type": "access",
        "exp": int(time.time()) + 60,
    })

    claims = validator.validate(token)
    assert claims.user_id == user_id
    assert claims.tenant_id == tenant_id
    assert claims.email == "a@b.com"


def test_rejects_expired():
    validator = MarsJwtValidator(SECRET)
    token = _make_token({
        "sub": str(uuid.uuid4()),
        "type": "access",
        "exp": int(time.time()) - 10,
    })

    with pytest.raises(MarsAuthError, match="expired"):
        validator.validate(token)


def test_rejects_refresh_token():
    validator = MarsJwtValidator(SECRET)
    token = _make_token({
        "sub": str(uuid.uuid4()),
        "type": "refresh",
        "exp": int(time.time()) + 60,
    })

    with pytest.raises(MarsAuthError, match="access"):
        validator.validate(token)


def test_rejects_bad_signature():
    validator = MarsJwtValidator(SECRET)
    token = _make_token(
        {"sub": str(uuid.uuid4()), "type": "access", "exp": int(time.time()) + 60},
        secret="wrong-secret",
    )

    with pytest.raises(MarsAuthError):
        validator.validate(token)


def test_accepts_missing_tenant_id():
    """Multi-tenant user: token ha type+sub+exp+email ma NO tenant_id."""
    validator = MarsJwtValidator(SECRET)
    token = _make_token({
        "sub": str(uuid.uuid4()),
        "email": "a@b.com",
        "type": "access",
        "exp": int(time.time()) + 60,
    })

    claims = validator.validate(token)
    assert claims.tenant_id is None
```

- [ ] **Step 2.4: Run test**

```bash
pytest tests/unit/test_mars_jwt_validator.py -v
```

Expected: 5/5 PASS.

- [ ] **Step 2.5: Commit**

```bash
git add src/infrastructure/mars/jwt_validator.py src/bootstrap/config.py .env.example tests/unit/test_mars_jwt_validator.py
git commit -m "Wave 26.2: Add MarsJwtValidator (shared secret HS256)

Validates MARS-issued JWT tokens locally (no network call).
Supports tenant_id claim (M5) as optional.
Rejects expired, refresh-type, bad-signature, malformed tokens.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: TenantId resolver con cache Redis

**Scope:** Se JWT ha `tenant_id` claim, usa quello. Altrimenti, chiama `GET /me` su MARS e cache in Redis per 5 minuti.

**Files:**
- Create: `src/infrastructure/mars/tenant_resolver.py`
- Test: `tests/unit/test_tenant_resolver.py`

- [ ] **Step 3.1: Implementa resolver**

File: `src/infrastructure/mars/tenant_resolver.py`

```python
"""Resolve tenantId from JWT or MARS /me endpoint with Redis cache."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

import redis.asyncio as aioredis

from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import MarsAuthError
from src.infrastructure.mars.jwt_validator import MarsJwtClaims

logger = logging.getLogger(__name__)


@dataclass
class MarsContext:
    """Resolved MARS user context (claims + enriched data)."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    enabled_modules: list[str]
    tenant_count: int  # 1 or more
    raw_token: str


class TenantResolver:
    """Resolves tenant + enabled modules from JWT or MARS /me.

    Cache strategy:
    - Key: `mars:user:{user_id}`
    - TTL: 300s (5 min)
    - Invalidation: upon 401 from MARS API
    """

    CACHE_TTL_SECONDS = 300

    def __init__(
        self,
        mars_client: MarsApiClient,
        redis_client: aioredis.Redis,
        cache_ttl: int = CACHE_TTL_SECONDS,
    ):
        self._mars = mars_client
        self._redis = redis_client
        self._ttl = cache_ttl

    async def resolve(self, claims: MarsJwtClaims, token: str) -> MarsContext:
        """Resolve full context for an authenticated user.

        Order:
        1. If JWT has tenant_id: use it directly (still fetch enabled_modules via cache)
        2. Otherwise: fetch via GET /me (cached)
        """
        cached = await self._get_cached(claims.user_id)
        if cached:
            # If JWT has tenant_id, use that (overrides cache in multi-tenant ambiguity)
            tenant_id = claims.tenant_id or cached["tenant_id"]
            if not tenant_id:
                raise MarsAuthError(f"User {claims.user_id} has no tenant (multi-tenant ambiguous)")
            return MarsContext(
                user_id=claims.user_id,
                tenant_id=uuid.UUID(str(tenant_id)),
                email=claims.email or cached.get("email", ""),
                enabled_modules=cached.get("enabled_modules", []),
                tenant_count=cached.get("tenant_count", 1),
                raw_token=token,
            )

        # Cache miss → call MARS
        me = await self._mars.get_me(token)

        tenant_id = claims.tenant_id or me.tenant_id
        if not tenant_id:
            raise MarsAuthError(
                f"User {claims.user_id} has no tenantId in JWT or /me response "
                f"(tenants count: {len(me.tenants)})"
            )

        ctx = MarsContext(
            user_id=claims.user_id,
            tenant_id=tenant_id,
            email=me.email,
            enabled_modules=list(me.enabled_modules),
            tenant_count=len(me.tenants) or 1,
            raw_token=token,
        )

        await self._cache(ctx)
        return ctx

    async def invalidate(self, user_id: uuid.UUID):
        await self._redis.delete(self._cache_key(user_id))

    def _cache_key(self, user_id: uuid.UUID) -> str:
        return f"mars:user:{user_id}"

    async def _cache(self, ctx: MarsContext):
        data = {
            "tenant_id": str(ctx.tenant_id),
            "email": ctx.email,
            "enabled_modules": ctx.enabled_modules,
            "tenant_count": ctx.tenant_count,
        }
        await self._redis.setex(
            self._cache_key(ctx.user_id),
            self._ttl,
            json.dumps(data),
        )

    async def _get_cached(self, user_id: uuid.UUID) -> Optional[dict]:
        raw = await self._redis.get(self._cache_key(user_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupted cache entry for user %s; evicting", user_id)
            await self._redis.delete(self._cache_key(user_id))
            return None
```

- [ ] **Step 3.2: Test**

File: `tests/unit/test_tenant_resolver.py`

```python
"""Unit tests for TenantResolver."""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.mars.tenant_resolver import TenantResolver
from src.infrastructure.mars.jwt_validator import MarsJwtClaims
from src.infrastructure.mars.exceptions import MarsAuthError
from src.infrastructure.mars.types import MarsMeResponse


@pytest.fixture
def redis_mock():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    r.delete = AsyncMock()
    return r


@pytest.fixture
def mars_mock():
    m = MagicMock()
    m.get_me = AsyncMock()
    return m


@pytest.mark.asyncio
async def test_resolves_from_jwt_tenant_id(redis_mock, mars_mock):
    resolver = TenantResolver(mars_mock, redis_mock)
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    # JWT has tenant_id; cache has enabled_modules
    import json
    redis_mock.get = AsyncMock(return_value=json.dumps({
        "tenant_id": str(tenant_id),
        "email": "a@b.com",
        "enabled_modules": ["dvr", "noise"],
        "tenant_count": 1,
    }).encode())

    claims = MarsJwtClaims(user_id=user_id, email="a@b.com", tenant_id=tenant_id, token_type="access")
    ctx = await resolver.resolve(claims, token="t")

    assert ctx.tenant_id == tenant_id
    assert "noise" in ctx.enabled_modules
    mars_mock.get_me.assert_not_called()


@pytest.mark.asyncio
async def test_calls_me_on_cache_miss(redis_mock, mars_mock):
    resolver = TenantResolver(mars_mock, redis_mock)
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    mars_mock.get_me.return_value = MarsMeResponse(
        userId=str(user_id),
        email="a@b.com",
        tenantId=str(tenant_id),
        tenants=[],
        enabledModules=["dvr", "noise"],
    )

    claims = MarsJwtClaims(user_id=user_id, email="a@b.com", tenant_id=None, token_type="access")
    ctx = await resolver.resolve(claims, token="t")

    assert ctx.tenant_id == tenant_id
    mars_mock.get_me.assert_called_once()
    redis_mock.setex.assert_called_once()


@pytest.mark.asyncio
async def test_raises_when_no_tenant_available(redis_mock, mars_mock):
    resolver = TenantResolver(mars_mock, redis_mock)
    user_id = uuid.uuid4()

    mars_mock.get_me.return_value = MarsMeResponse(
        userId=str(user_id),
        email="a@b.com",
        tenantId=None,
        tenants=[],  # empty
        enabledModules=[],
    )

    claims = MarsJwtClaims(user_id=user_id, email="a@b.com", tenant_id=None, token_type="access")

    with pytest.raises(MarsAuthError, match="no tenantId"):
        await resolver.resolve(claims, token="t")
```

- [ ] **Step 3.3: Run**

```bash
pytest tests/unit/test_tenant_resolver.py -v
```

Expected: 3/3 PASS.

- [ ] **Step 3.4: Commit**

```bash
git add src/infrastructure/mars/tenant_resolver.py tests/unit/test_tenant_resolver.py
git commit -m "Wave 26.3: Add TenantResolver with Redis cache (5min TTL)

Resolves MarsContext from JWT claims or GET /me fallback.
Caches enabled_modules + tenantId in Redis to minimize MARS API load.
Invalidation on MarsAuthError (caller responsibility).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: FastAPI dependency `require_mars_context`

**Scope:** Middleware/dependency che valida JWT, resolve tenantId, verifica modulo abilitato. Ogni route noise-specific usa questa.

**Files:**
- Create: `src/api/dependencies/mars.py`
- Test: `tests/api/test_mars_dependency.py`

- [ ] **Step 4.1: Implementa dependency**

File: `src/api/dependencies/mars.py`

```python
"""FastAPI dependency for MARS context injection."""
from __future__ import annotations

from typing import Annotated, AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, status

from src.bootstrap.config import Settings, get_settings
from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import MarsAuthError, MarsPaymentRequiredError
from src.infrastructure.mars.jwt_validator import MarsJwtValidator
from src.infrastructure.mars.tenant_resolver import MarsContext, TenantResolver


_mars_client_singleton: MarsApiClient | None = None


async def get_mars_client(settings: Settings = Depends(get_settings)) -> MarsApiClient:
    global _mars_client_singleton
    if _mars_client_singleton is None:
        _mars_client_singleton = MarsApiClient(base_url=settings.mars_api_base_url)
    return _mars_client_singleton


async def get_redis_client(settings: Settings = Depends(get_settings)) -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=False)


def get_jwt_validator(settings: Settings = Depends(get_settings)) -> MarsJwtValidator:
    return MarsJwtValidator(
        secret=settings.mars_jwt_access_secret,
        algorithm=settings.mars_jwt_algorithm,
    )


async def get_tenant_resolver(
    mars: Annotated[MarsApiClient, Depends(get_mars_client)],
    redis: Annotated[aioredis.Redis, Depends(get_redis_client)],
) -> TenantResolver:
    return TenantResolver(mars, redis)


async def require_mars_context(
    authorization: Annotated[str | None, Header()] = None,
    validator: Annotated[MarsJwtValidator, Depends(get_jwt_validator)] = None,
    resolver: Annotated[TenantResolver, Depends(get_tenant_resolver)] = None,
    mars: Annotated[MarsApiClient, Depends(get_mars_client)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> MarsContext:
    """Extract + validate JWT, resolve tenant, verify module access."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]

    try:
        claims = validator.validate(token)
    except MarsAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        context = await resolver.resolve(claims, token)
    except MarsAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    # Verify module access
    module_key = settings.mars_module_key
    if module_key not in context.enabled_modules:
        # Verify live against MARS (may have changed after cache)
        try:
            verify = await mars.verify_module(token, module_key)
        except MarsAuthError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

        if not verify.enabled:
            if verify.reason == "not-purchased":
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"Module '{module_key}' not enabled for tenant",
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{module_key}' not available: {verify.reason}",
            )

        # Update cache async
        await resolver.invalidate(claims.user_id)

    return context
```

- [ ] **Step 4.2: Test**

File: `tests/api/test_mars_dependency.py`

```python
"""Integration test for require_mars_context dependency."""
import pytest
import uuid
import jwt
import time
from httpx import AsyncClient

from src.bootstrap.main import app


@pytest.fixture
def valid_token(settings):
    return jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "a@b.com",
            "tenant_id": str(uuid.uuid4()),
            "type": "access",
            "exp": int(time.time()) + 60,
        },
        settings.mars_jwt_access_secret,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_missing_auth_returns_401(async_client: AsyncClient):
    response = await async_client.get("/api/v1/noise/assessments")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(async_client: AsyncClient):
    response = await async_client.get(
        "/api/v1/noise/assessments",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_token_reaches_route(async_client: AsyncClient, valid_token, mock_mars_api):
    """With mocked MARS and valid token, route should respond 200 (or route-specific)."""
    mock_mars_api.get_me.return_value.enabled_modules = ["dvr", "noise"]

    response = await async_client.get(
        "/api/v1/noise/assessments",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    # Expected: not 401/402/403 (route-specific status codes are OK)
    assert response.status_code not in (401, 402, 403)
```

Nota: `mock_mars_api` è un fixture che il test framework deve fornire. Aggiungi in `tests/conftest.py`:

```python
@pytest.fixture
def mock_mars_api(monkeypatch):
    """Mocks MarsApiClient methods used by dependencies."""
    from unittest.mock import AsyncMock, MagicMock
    client = MagicMock()
    client.get_me = AsyncMock()
    client.verify_module = AsyncMock(return_value=MagicMock(enabled=True, module_key="noise"))
    monkeypatch.setattr("src.api.dependencies.mars._mars_client_singleton", client)
    return client
```

- [ ] **Step 4.3: Run**

```bash
pytest tests/api/test_mars_dependency.py -v
```

- [ ] **Step 4.4: Commit**

```bash
git add src/api/dependencies/mars.py tests/api/test_mars_dependency.py tests/conftest.py
git commit -m "Wave 26.4: Add require_mars_context FastAPI dependency

Validates JWT, resolves tenantId via TenantResolver, verifies module
enabled via MarsApiClient. Returns MarsContext for downstream handlers.
Centralized auth for all noise-specific routes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: DvrSnapshotService

**Scope:** Service layer che fetcha DVR snapshot da MARS, fornisce helper parse, applica patch.

**Files:**
- Create: `src/application/services/dvr_snapshot_service.py`
- Test: `tests/unit/test_dvr_snapshot_service.py`

- [ ] **Step 5.1: Implementa service**

File: `src/application/services/dvr_snapshot_service.py`

```python
"""Service for fetching and patching MARS DVR snapshots."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import MarsConflictError, MarsNotFoundError
from src.infrastructure.mars.types import MarsDvrRevisionResponse, MarsDvrSnapshot

logger = logging.getLogger(__name__)

MODULE_VERSION = "0.1.0"
MODULE_KEY = "noise"


class DvrSnapshotService:
    def __init__(self, mars_client: MarsApiClient):
        self._mars = mars_client

    async def fetch_revision(
        self,
        token: str,
        document_id: uuid.UUID,
        revision_id: uuid.UUID,
    ) -> MarsDvrRevisionResponse:
        return await self._mars.get_dvr_revision(token, document_id, revision_id)

    def extract_noise_sources_candidates(self, snapshot: MarsDvrSnapshot) -> list[dict[str, Any]]:
        """Estrae equipment candidati come sorgenti rumore dal DVR snapshot.

        Returns: lista di {phase_id, equipment_id, brand, model, tipology}.
        """
        candidates = []
        phase_names = {p.id: p.name for p in snapshot.work_phases}

        for eq in snapshot.phase_equipments:
            candidates.append({
                "phase_id": eq.phase_id,
                "phase_name": phase_names.get(eq.phase_id, ""),
                "equipment_id": eq.id,
                "brand": eq.brand,
                "model": eq.model,
                "tipology": eq.tipology,
            })
        return candidates

    async def write_module_extension(
        self,
        token: str,
        document_id: uuid.UUID,
        revision_id: uuid.UUID,
        expected_version: int,
        assessment_context_id: uuid.UUID,
        summary: dict[str, Any],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Scrive/aggiorna `module_extensions.noise` nel DVR snapshot MARS.

        Ritorna il nuovo version number.
        Raises MarsConflictError se version mismatch (optimistic lock).
        """
        payload = {
            "module_version": MODULE_VERSION,
            "assessment_context_id": str(assessment_context_id),
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "data": data,
        }

        try:
            return await self._mars.put_module_extension(
                token=token,
                document_id=document_id,
                revision_id=revision_id,
                module_key=MODULE_KEY,
                expected_version=expected_version,
                payload=payload,
            )
        except MarsConflictError as exc:
            logger.warning(
                "Version conflict writing module_extensions.noise for revision %s: expected %d, current %s",
                revision_id,
                expected_version,
                exc.payload.get("currentVersion") if exc.payload else "?",
            )
            raise
```

- [ ] **Step 5.2: Test**

File: `tests/unit/test_dvr_snapshot_service.py`

```python
"""Unit tests for DvrSnapshotService."""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

from src.application.services.dvr_snapshot_service import DvrSnapshotService
from src.infrastructure.mars.types import (
    MarsDvrCompanyData,
    MarsDvrPhaseEquipment,
    MarsDvrRevisionResponse,
    MarsDvrSnapshot,
    MarsDvrWorkPhase,
)


@pytest.fixture
def mock_mars():
    m = MagicMock()
    m.get_dvr_revision = AsyncMock()
    m.put_module_extension = AsyncMock(return_value={"version": 7})
    return m


def _make_snapshot():
    return MarsDvrSnapshot(
        schemaVersion="1.1.0",
        companyData=MarsDvrCompanyData(vatNumber="123", legalName="ACME", atecoCode="62.02"),
        workPhases=[
            MarsDvrWorkPhase(id="p1", name="Tornitura"),
            MarsDvrWorkPhase(id="p2", name="Fresatura"),
        ],
        phaseEquipments=[
            MarsDvrPhaseEquipment(id="e1", phaseId="p1", brand="Mazak", model="QuickTurn 200", tipology="CNC lathe"),
            MarsDvrPhaseEquipment(id="e2", phaseId="p2", brand="Haas", model="VF-2", tipology="CNC mill"),
        ],
    )


@pytest.mark.asyncio
async def test_extract_noise_candidates(mock_mars):
    service = DvrSnapshotService(mock_mars)
    snapshot = _make_snapshot()

    candidates = service.extract_noise_sources_candidates(snapshot)
    assert len(candidates) == 2
    assert candidates[0]["phase_name"] == "Tornitura"
    assert candidates[0]["brand"] == "Mazak"


@pytest.mark.asyncio
async def test_fetch_revision(mock_mars):
    service = DvrSnapshotService(mock_mars)
    rev_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    mock_mars.get_dvr_revision.return_value = MarsDvrRevisionResponse(
        id=rev_id,
        documentId=doc_id,
        tenantId=tenant_id,
        version=3,
        status="draft",
        snapshot=_make_snapshot(),
        createdAt="2026-04-17T10:00:00Z",
        updatedAt="2026-04-17T10:00:00Z",
    )

    result = await service.fetch_revision("t", doc_id, rev_id)
    assert result.version == 3
    assert len(result.snapshot.work_phases) == 2


@pytest.mark.asyncio
async def test_write_module_extension(mock_mars):
    service = DvrSnapshotService(mock_mars)
    doc_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    ctx_id = uuid.uuid4()

    result = await service.write_module_extension(
        token="t",
        document_id=doc_id,
        revision_id=rev_id,
        expected_version=6,
        assessment_context_id=ctx_id,
        summary={"lex_8h": 85.2, "risk_band": "ORANGE"},
        data={"phases": []},
    )

    assert result["version"] == 7
    call_kwargs = mock_mars.put_module_extension.call_args.kwargs
    assert call_kwargs["module_key"] == "noise"
    assert call_kwargs["expected_version"] == 6
    assert call_kwargs["payload"]["module_version"] == "0.1.0"
    assert call_kwargs["payload"]["assessment_context_id"] == str(ctx_id)
```

- [ ] **Step 5.3: Run**

```bash
pytest tests/unit/test_dvr_snapshot_service.py -v
```

Expected: 3/3 PASS.

- [ ] **Step 5.4: Commit**

```bash
git add src/application/services/dvr_snapshot_service.py tests/unit/test_dvr_snapshot_service.py
git commit -m "Wave 26.5: Add DvrSnapshotService (fetch + patch helpers)

fetch_revision(): GET DVR from MARS with typed response.
extract_noise_sources_candidates(): normalizes equipment for AI pipeline.
write_module_extension(): PUT patch with optimistic lock + module_version.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Refactor route esistenti per usare MARS context

**Scope:** Le route `assessments.py`, `ai_routes.py`, `export_routes.py` attualmente usano `current_user: User = Depends(...)` con user locale. Vanno sostituite con `mars_ctx: MarsContext = Depends(require_mars_context)`.

**Files (tutti modify):**
- `src/api/routes/assessments.py`
- `src/api/routes/ai_routes.py`
- `src/api/routes/export_routes.py`
- `src/api/routes/companies.py`
- `src/api/routes/job_roles.py`
- `src/api/routes/mitigations.py`
- `src/api/routes/machine_assets.py`
- `src/api/routes/rag_routes.py`
- `src/api/routes/admin.py`

- [ ] **Step 6.1: Grep all uses of legacy auth**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore"
grep -rn "Depends(get_current_user)" src/api/routes/ | tee /tmp/legacy_auth_routes.txt
grep -rn "from src.infrastructure.auth" src/api/routes/ | tee -a /tmp/legacy_auth_routes.txt
wc -l /tmp/legacy_auth_routes.txt
```

- [ ] **Step 6.2: Refactor pattern**

Per ogni route, sostituisci:

```python
# BEFORE
from src.infrastructure.auth.dependencies import get_current_user
from src.infrastructure.database.models.user import User

@router.get("/assessments")
async def list_assessments(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # query filter: .where(NoiseAssessment.tenant_id == current_user.tenant_id)
    ...
```

con:

```python
# AFTER
from src.api.dependencies.mars import require_mars_context
from src.infrastructure.mars.tenant_resolver import MarsContext

@router.get("/assessments")
async def list_assessments(
    mars_ctx: MarsContext = Depends(require_mars_context),
    session: AsyncSession = Depends(get_session),
):
    # query filter: .where(NoiseAssessmentContext.mars_tenant_id == mars_ctx.tenant_id)
    ...
```

- [ ] **Step 6.3: Per ogni route, update queries**

Esempio `assessments.py`:

```python
# BEFORE (using NoiseAssessment.tenant_id with local tenant)
stmt = select(NoiseAssessment).where(NoiseAssessment.tenant_id == current_user.tenant_id)

# AFTER (using context.mars_tenant_id via NoiseAssessmentContext)
stmt = (
    select(NoiseAssessment)
    .join(NoiseAssessmentContext, NoiseAssessment.context_id == NoiseAssessmentContext.id)
    .where(NoiseAssessmentContext.mars_tenant_id == mars_ctx.tenant_id)
    .where(NoiseAssessmentContext.deleted_at.is_(None))
)
```

- [ ] **Step 6.4: Create endpoint `POST /api/v1/noise/contexts/bootstrap`**

Nuovo endpoint che crea `NoiseAssessmentContext` fetchando DVR MARS.

File: `src/api/routes/contexts.py` (nuovo)

```python
"""Bootstrap noise assessment from MARS DVR revision."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.mars import require_mars_context
from src.api.schemas.noise_context import NoiseAssessmentContextRead
from src.application.services.dvr_snapshot_service import DvrSnapshotService
from src.bootstrap.database import get_session
from src.infrastructure.database.models.noise_assessment_context import NoiseAssessmentContext
from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.tenant_resolver import MarsContext
from src.api.dependencies.mars import get_mars_client

router = APIRouter(prefix="/api/v1/noise/contexts", tags=["contexts"])


class BootstrapRequest(BaseModel):
    mars_dvr_document_id: uuid.UUID
    mars_revision_id: uuid.UUID


@router.post("/bootstrap", response_model=NoiseAssessmentContextRead, status_code=status.HTTP_201_CREATED)
async def bootstrap_context(
    payload: BootstrapRequest,
    mars_ctx: MarsContext = Depends(require_mars_context),
    mars: MarsApiClient = Depends(get_mars_client),
    session: AsyncSession = Depends(get_session),
):
    # 1. Fetch DVR from MARS
    svc = DvrSnapshotService(mars)
    try:
        revision = await svc.fetch_revision(
            token=mars_ctx.raw_token,
            document_id=payload.mars_dvr_document_id,
            revision_id=payload.mars_revision_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"MARS fetch failed: {exc}")

    # 2. Verify tenant match
    if revision.tenant_id != mars_ctx.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    # 3. Check existing context (idempotency)
    from sqlalchemy import select
    stmt = (
        select(NoiseAssessmentContext)
        .where(NoiseAssessmentContext.mars_revision_id == payload.mars_revision_id)
        .where(NoiseAssessmentContext.deleted_at.is_(None))
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing

    # 4. Create context
    from src.infrastructure.database.models.noise_assessment_context import (
        NoiseAssessmentContext,
    )
    context = NoiseAssessmentContext(
        mars_dvr_document_id=payload.mars_dvr_document_id,
        mars_revision_id=payload.mars_revision_id,
        mars_revision_version=revision.version,
        mars_tenant_id=mars_ctx.tenant_id,
        mars_company_id=uuid.uuid4(),  # TODO: derive from snapshot
        ateco_code=revision.snapshot.company_data.ateco_code,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(context)
    await session.commit()
    await session.refresh(context)

    return context
```

- [ ] **Step 6.5: Registra router**

File: `src/bootstrap/main.py` — aggiungi:

```python
from src.api.routes.contexts import router as contexts_router
app.include_router(contexts_router)
```

- [ ] **Step 6.6: Run tests regression**

```bash
make test
```

Expected: tutti passing (alcuni test che usano old auth potrebbero fallire se non aggiornati; fix-li se necessario).

- [ ] **Step 6.7: Commit (atomico per file)**

```bash
git add src/api/routes/assessments.py
git commit -m "Wave 26.6a: Refactor assessments routes to use require_mars_context"

git add src/api/routes/ai_routes.py
git commit -m "Wave 26.6b: Refactor ai_routes to use require_mars_context"

# ... per ogni file refactored

git add src/api/routes/contexts.py src/bootstrap/main.py
git commit -m "Wave 26.6z: Add POST /contexts/bootstrap endpoint

Creates NoiseAssessmentContext by fetching MARS DVR revision.
Idempotent on (mars_revision_id) if deleted_at IS NULL.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Apply Migration 016 (drop duplicates)

**Pre-req:** Task 6 completata, grep conferma zero uso di `Company`, `User`, `Tenant` locali nelle route/services.

- [ ] **Step 7.1: Final grep**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore"
grep -rn "from src.infrastructure.database.models.company" src/ tests/
grep -rn "from src.infrastructure.database.models.user" src/ tests/ | grep -v "user_role"
grep -rn "from src.infrastructure.database.models.tenant" src/ tests/
```

Expected: risultati solo in `__init__.py` models (export) o in vecchi test da aggiornare.

- [ ] **Step 7.2: Rimuovi export da `__init__.py`**

File: `src/infrastructure/database/models/__init__.py`

Rimuovi import + export di `Company`, `User`, `UserRole`, `Tenant`.

- [ ] **Step 7.3: Apply migration 016**

```bash
alembic upgrade 016
```

Expected: no errori.

- [ ] **Step 7.4: Run full test**

```bash
make test
```

- [ ] **Step 7.5: Update STATUS.md**

Segna 016 come applicata.

- [ ] **Step 7.6: Commit**

```bash
git add src/infrastructure/database/models/__init__.py docs/superpowers/plans/STATUS.md
git commit -m "Wave 26.7: Apply migration 016 — drop Company/User/Tenant locals

Code no longer imports local models. Migration applied.
Rumore is now fully thin plugin.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Outbox helper service + emit eventi

**Scope:** Ogni modifica a entità rumore-specifiche emette un evento in `rumore_outbox`. Helper condiviso.

**Files:**
- Create: `src/application/services/outbox_service.py`
- Test: `tests/unit/test_outbox_service.py`

- [ ] **Step 8.1: Implementa service**

File: `src/application/services/outbox_service.py`

```python
"""Outbox pattern: emit events from domain operations for future cloud sync."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.outbox import RumoreOutbox

logger = logging.getLogger(__name__)


class OutboxService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def emit(
        self,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> RumoreOutbox:
        """Insert an event into outbox. Dispatcher will deliver later."""
        event = RumoreOutbox(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload_json=payload,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(event)
        logger.debug("Emitted outbox event %s for %s %s", event_type, aggregate_type, aggregate_id)
        return event
```

- [ ] **Step 8.2: Test**

File: `tests/unit/test_outbox_service.py`

```python
import pytest
import uuid

from src.application.services.outbox_service import OutboxService
from src.infrastructure.database.models.outbox import RumoreOutbox


@pytest.mark.asyncio
async def test_emit_creates_outbox_row(async_session):
    service = OutboxService(async_session)
    aggregate_id = uuid.uuid4()

    event = await service.emit(
        aggregate_type="noise_assessment_context",
        aggregate_id=aggregate_id,
        event_type="noise.context.created",
        payload={"foo": "bar"},
    )

    await async_session.commit()
    await async_session.refresh(event)

    assert event.id is not None
    assert event.dispatched_at is None
    assert event.payload_json == {"foo": "bar"}
```

- [ ] **Step 8.3: Run + commit**

```bash
pytest tests/unit/test_outbox_service.py -v
git add src/application/services/outbox_service.py tests/unit/test_outbox_service.py
git commit -m "Wave 26.8: Add OutboxService for event emission

Helper to insert events into rumore_outbox table. Cloud-native readiness:
events consumed by scheduler dispatcher (log-only today, cloud-pusher
when MARS cloud-native exists).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Lint + test + push

- [ ] **Step 9.1: Lint**

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

- [ ] **Step 9.2: Full test**

```bash
make test
```

- [ ] **Step 9.3: Push**

```bash
git push
```

- [ ] **Step 9.4: STATUS.md update**

Aggiorna `docs/superpowers/plans/STATUS.md` con W26 ✅.

---

## Acceptance criteria Wave 26

1. ✅ `MarsApiClient` con 7 metodi (get_me, verify_module, register_session, heartbeat_session, end_session, get_dvr_revision, put_module_extension) + 7 test passing
2. ✅ `MarsJwtValidator` valida token MARS con shared secret + 5 test passing
3. ✅ `TenantResolver` con cache Redis 5min TTL + 3 test passing
4. ✅ `require_mars_context` FastAPI dependency + integration test
5. ✅ `DvrSnapshotService` con 3 helpers + 3 test passing
6. ✅ Tutte le route noise usano `require_mars_context` (nessun `get_current_user` residuo)
7. ✅ Endpoint nuovo `POST /api/v1/noise/contexts/bootstrap`
8. ✅ Migration 016 applicata (drop Company/User/Tenant)
9. ✅ `OutboxService` + test
10. ✅ `make test` passing
11. ✅ Push branch

---

## Rollback Wave 26

```bash
# Git
git reset --hard <SHA pre-wave26>
git push --force-with-lease  # solo se autorizzato

# DB (se applicato 016):
alembic downgrade 015

# Feature flag env (rapido):
REQUIRE_MARS_CONTEXT=false
```

Con `REQUIRE_MARS_CONTEXT=false`, il modulo torna a usare il legacy auth (se il codice lo supporta ancora — valuta se tenere un toggle).

---

## Next Wave

**Wave 27 — AI Autopilot** (`2026-04-17-wave-27-ai-autopilot.md`)

Richiede: Wave 25 (NoiseAssessmentContext) + Wave 26 (DvrSnapshotService).
