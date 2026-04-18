"""Unit tests for MarsApiClient.

Uses httpx.MockTransport (built-in) — no external test deps required.
Each test supplies its own handler that returns canned responses.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.exceptions import (
    MarsAuthError,
    MarsConflictError,
    MarsNotFoundError,
    MarsPaymentRequiredError,
    MarsUnavailableError,
    MarsValidationError,
)


TOKEN = "test-bearer-token"
DOC_ID = uuid.uuid4()
REV_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


# ── helpers ─────────────────────────────────────────────────────────


def _me_response_body() -> dict:
    return {
        "userId": str(USER_ID),
        "email": "user@example.com",
        "fullName": "Test User",
        "tenantId": str(TENANT_ID),
        "tenants": [{"id": str(TENANT_ID), "name": "ACME", "role": "admin"}],
        "enabledModules": ["noise", "vibrations"],
        "rolesByCompany": {"company-1": ["hse_consultant"]},
    }


def _revision_response_body(version: int = 1) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(REV_ID),
        "documentId": str(DOC_ID),
        "tenantId": str(TENANT_ID),
        "version": version,
        "status": "draft",
        "snapshot": {
            "schemaVersion": "1.1.0",
            "companyData": {"vatNumber": "IT00000000000", "legalName": "ACME SRL"},
            "workPhases": [{"id": "ph-1", "name": "Taglio"}],
            "phaseEquipments": [],
            "risks": [],
            "actions": [],
            "trainings": [],
            "module_extensions": {},
        },
        "createdAt": now,
        "updatedAt": now,
    }


def _handler(status: int, body: dict | str, *, headers: dict | None = None):
    """Build a MockTransport handler returning a single canned response."""

    def h(request: httpx.Request) -> httpx.Response:
        content = body if isinstance(body, str) else json.dumps(body)
        return httpx.Response(
            status,
            content=content,
            headers={"content-type": "application/json", **(headers or {})},
        )

    return h


# ── get_me ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_me_success():
    transport = httpx.MockTransport(_handler(200, _me_response_body()))
    async with MarsApiClient(base_url="http://mars.test", transport=transport) as cli:
        me = await cli.get_me(TOKEN)
    assert me.email == "user@example.com"
    assert me.tenant_id == TENANT_ID
    assert "noise" in me.enabled_modules
    assert me.roles_by_company == {"company-1": ["hse_consultant"]}


@pytest.mark.asyncio
async def test_get_me_sends_bearer_token():
    captured = {}

    def h(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["path"] = request.url.path
        return httpx.Response(200, json=_me_response_body())

    async with MarsApiClient(base_url="http://mars.test", transport=httpx.MockTransport(h)) as cli:
        await cli.get_me(TOKEN)

    assert captured["auth"] == f"Bearer {TOKEN}"
    assert captured["path"] == "/me"


@pytest.mark.asyncio
async def test_get_me_auth_error():
    transport = httpx.MockTransport(_handler(401, {"message": "expired"}))
    async with MarsApiClient(base_url="http://mars.test", transport=transport) as cli:
        with pytest.raises(MarsAuthError) as exc:
            await cli.get_me(TOKEN)
    assert exc.value.status_code == 401


# ── verify_module ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_module_enabled():
    transport = httpx.MockTransport(
        _handler(200, {"enabled": True, "moduleKey": "noise"})
    )
    async with MarsApiClient(base_url="http://mars.test", transport=transport) as cli:
        result = await cli.verify_module(TOKEN, "noise")
    assert result.enabled is True
    assert result.module_key == "noise"


@pytest.mark.asyncio
async def test_verify_module_payment_required():
    transport = httpx.MockTransport(
        _handler(402, {"message": "module not purchased"})
    )
    async with MarsApiClient(base_url="http://mars.test", transport=transport) as cli:
        with pytest.raises(MarsPaymentRequiredError):
            await cli.verify_module(TOKEN, "chemical")


# ── get_dvr_revision ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_dvr_revision_by_id():
    transport = httpx.MockTransport(_handler(200, _revision_response_body()))
    async with MarsApiClient(base_url="http://mars.test", transport=transport) as cli:
        rev = await cli.get_dvr_revision(TOKEN, DOC_ID, REV_ID)
    assert rev.version == 1
    assert rev.snapshot.schema_version == "1.1.0"
    assert rev.snapshot.company_data.vat_number == "IT00000000000"
    assert len(rev.snapshot.work_phases) == 1


@pytest.mark.asyncio
async def test_get_dvr_revision_latest_when_none():
    captured = {}

    def h(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json=_revision_response_body())

    async with MarsApiClient(base_url="http://mars.test", transport=httpx.MockTransport(h)) as cli:
        await cli.get_dvr_revision(TOKEN, DOC_ID)

    assert captured["path"] == f"/dvr-documents/{DOC_ID}/revisions/latest"


@pytest.mark.asyncio
async def test_get_dvr_revision_not_found():
    transport = httpx.MockTransport(_handler(404, {"message": "not found"}))
    async with MarsApiClient(base_url="http://mars.test", transport=transport) as cli:
        with pytest.raises(MarsNotFoundError):
            await cli.get_dvr_revision(TOKEN, DOC_ID, REV_ID)


# ── put_module_extensions ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_put_module_extensions_with_if_match():
    captured = {}

    def h(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["if_match"] = request.headers.get("if-match")
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_revision_response_body(version=2))

    async with MarsApiClient(base_url="http://mars.test", transport=httpx.MockTransport(h)) as cli:
        rev = await cli.put_module_extensions(
            TOKEN, DOC_ID, REV_ID, "noise",
            {"module_version": "0.1.0", "summary": {"lex_8h": 85.2}},
            if_match_version=1,
        )

    assert captured["method"] == "PUT"
    assert captured["path"].endswith(f"/module-extensions/noise")
    assert captured["if_match"] == "1"
    assert captured["body"]["summary"]["lex_8h"] == 85.2
    assert rev.version == 2


@pytest.mark.asyncio
async def test_put_module_extensions_conflict():
    transport = httpx.MockTransport(
        _handler(409, {"message": "version mismatch"})
    )
    async with MarsApiClient(base_url="http://mars.test", transport=transport) as cli:
        with pytest.raises(MarsConflictError):
            await cli.put_module_extensions(
                TOKEN, DOC_ID, REV_ID, "noise", {"x": 1}, if_match_version=3
            )


@pytest.mark.asyncio
async def test_put_module_extensions_validation_error():
    transport = httpx.MockTransport(
        _handler(422, {"message": "schema violation", "errors": ["missing module_version"]})
    )
    async with MarsApiClient(base_url="http://mars.test", transport=transport) as cli:
        with pytest.raises(MarsValidationError):
            await cli.put_module_extensions(TOKEN, DOC_ID, REV_ID, "noise", {})


# ── register_module_session ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_module_session():
    transport = httpx.MockTransport(
        _handler(201, {
            "sessionId": "sess-1",
            "moduleKey": "noise",
            "revisionVersion": 1,
            "startedAt": datetime.now(timezone.utc).isoformat(),
        })
    )
    async with MarsApiClient(base_url="http://mars.test", transport=transport) as cli:
        session = await cli.register_module_session(TOKEN, DOC_ID, REV_ID, "noise")
    assert session.session_id == "sess-1"
    assert session.module_key == "noise"


# ── retry behavior ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retry_on_5xx_then_success():
    call_count = {"n": 0}

    def h(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] < 3:
            return httpx.Response(503, json={"message": "overloaded"})
        return httpx.Response(200, json=_me_response_body())

    async with MarsApiClient(
        base_url="http://mars.test",
        transport=httpx.MockTransport(h),
        max_retries=3,
    ) as cli:
        me = await cli.get_me(TOKEN)

    assert call_count["n"] == 3
    assert me.email == "user@example.com"


@pytest.mark.asyncio
async def test_retry_exhausted_raises_unavailable():
    def h(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "boom"})

    async with MarsApiClient(
        base_url="http://mars.test",
        transport=httpx.MockTransport(h),
        max_retries=1,  # fast test
    ) as cli:
        with pytest.raises(MarsUnavailableError) as exc:
            await cli.get_me(TOKEN)
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_no_retry_on_4xx():
    call_count = {"n": 0}

    def h(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(404, json={"message": "nope"})

    async with MarsApiClient(
        base_url="http://mars.test",
        transport=httpx.MockTransport(h),
        max_retries=3,
    ) as cli:
        with pytest.raises(MarsNotFoundError):
            await cli.get_dvr_revision(TOKEN, DOC_ID, REV_ID)

    # 4xx should not trigger retry — single call
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_transport_error_retries():
    call_count = {"n": 0}

    def h(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json=_me_response_body())

    async with MarsApiClient(
        base_url="http://mars.test",
        transport=httpx.MockTransport(h),
        max_retries=2,
    ) as cli:
        me = await cli.get_me(TOKEN)

    assert call_count["n"] == 2
    assert me.email == "user@example.com"
