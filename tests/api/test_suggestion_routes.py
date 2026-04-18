"""API tests for /api/v1/noise/suggestions/* (V2 context-scoped)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from src.api.dependencies.mars import get_mars_client, require_mars_context
from src.bootstrap.main import app
from src.infrastructure.database.models.ai_suggestion import (
    AISuggestion,
)
from src.infrastructure.database.models.noise_assessment_context import (
    NoiseAssessmentContext,
)
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.mars.types import MarsContext

PREFIX = "/api/v1/noise"


@pytest.fixture(autouse=True)
def _configure_mars_for_tests(monkeypatch):
    from src.api.dependencies.mars import reset_mars_singletons
    from src.bootstrap.config import get_settings

    monkeypatch.setenv("MARS_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("MARS_JWT_HS256_SECRET", "x" * 32)
    get_settings.cache_clear()
    reset_mars_singletons()
    yield
    get_settings.cache_clear()
    reset_mars_singletons()


@pytest.fixture
async def seeded(db_session):
    """Seed tenant + context + 3 suggestions; return (tenant, ctx, suggestions)."""
    tenant = Tenant(id=uuid.uuid4(), name="T", slug=f"t-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()

    ctx = NoiseAssessmentContext(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=uuid.uuid4(),
        mars_dvr_document_id=uuid.uuid4(),
        mars_revision_id=uuid.uuid4(),
        mars_document_version=1,
        status="bootstrapped",
    )
    db_session.add(ctx)
    await db_session.flush()

    sugg_list: list[AISuggestion] = []
    for i, (status, confidence) in enumerate([("pending", 0.9), ("pending", 0.4), ("approved", 0.8)]):
        s = AISuggestion(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            context_id=ctx.id,
            suggestion_type="phase_laeq",
            title=f"Suggerimento {i}",
            content={"laeq_db": 85.0 + i, "duration_hours": 2.0, "phase_name": f"Phase {i}"},
            confidence_score=confidence,
            status=status,
        )
        db_session.add(s)
        sugg_list.append(s)
    await db_session.flush()

    return tenant, ctx, sugg_list


@pytest.fixture
def mars_override(seeded):
    tenant, ctx, sugg = seeded
    mars_ctx = MarsContext(
        user_id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="hse@example.com",
        enabled_modules=["noise"],
        access_token="bearer-test",
    )
    app.dependency_overrides[require_mars_context] = lambda: mars_ctx
    # Minimal mock client, unused by suggestion routes
    import httpx

    from src.infrastructure.mars.client import MarsApiClient

    client = MarsApiClient(
        base_url="http://mars.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        max_retries=0,
    )
    app.dependency_overrides[get_mars_client] = lambda: client
    yield mars_ctx
    app.dependency_overrides.pop(require_mars_context, None)
    app.dependency_overrides.pop(get_mars_client, None)


# ── list ───────────────────────────────────────────────────────────


async def test_list_by_context(client: AsyncClient, seeded, mars_override):
    _, ctx, _ = seeded
    r = await client.get(f"{PREFIX}/suggestions/by-context/{ctx.id}")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 3
    keys = set(items[0].keys())
    # Shape matches frontend SuggestionCard expectations
    assert "payload_json" in keys
    assert "confidence" in keys
    assert "context_id" in keys


async def test_list_filters_by_status(client: AsyncClient, seeded, mars_override):
    _, ctx, _ = seeded
    r = await client.get(f"{PREFIX}/suggestions/by-context/{ctx.id}?status=pending")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert all(i["status"] == "pending" for i in items)


async def test_list_no_auth_returns_401(client: AsyncClient, seeded):
    _, ctx, _ = seeded
    r = await client.get(f"{PREFIX}/suggestions/by-context/{ctx.id}")
    assert r.status_code == 401


# ── approve ────────────────────────────────────────────────────────


async def test_approve_pending(client: AsyncClient, seeded, mars_override):
    _, _, sugg = seeded
    pending = [s for s in sugg if s.status == "pending"][0]

    r = await client.post(
        f"{PREFIX}/suggestions/{pending.id}/approve",
        json={},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert body["approved_by"] == "hse@example.com"


async def test_approve_with_edits(client: AsyncClient, seeded, mars_override):
    _, _, sugg = seeded
    pending = [s for s in sugg if s.status == "pending"][0]

    r = await client.post(
        f"{PREFIX}/suggestions/{pending.id}/approve",
        json={"edited_payload": {"laeq_db": 99.0, "duration_hours": 4.0}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["payload_json"]["laeq_db"] == 99.0


async def test_approve_already_approved_returns_409(client: AsyncClient, seeded, mars_override):
    _, _, sugg = seeded
    approved = [s for s in sugg if s.status == "approved"][0]

    r = await client.post(f"{PREFIX}/suggestions/{approved.id}/approve", json={})
    assert r.status_code == 409


async def test_approve_unknown_returns_404(client: AsyncClient, mars_override):
    r = await client.post(f"{PREFIX}/suggestions/{uuid.uuid4()}/approve", json={})
    assert r.status_code == 404


# ── reject ─────────────────────────────────────────────────────────


async def test_reject_with_reason(client: AsyncClient, seeded, mars_override):
    _, _, sugg = seeded
    pending = [s for s in sugg if s.status == "pending"][0]

    r = await client.post(
        f"{PREFIX}/suggestions/{pending.id}/reject",
        json={"reason": "Non applicabile"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Non applicabile"


async def test_reject_already_approved_returns_409(client: AsyncClient, seeded, mars_override):
    _, _, sugg = seeded
    approved = [s for s in sugg if s.status == "approved"][0]

    r = await client.post(f"{PREFIX}/suggestions/{approved.id}/reject", json={"reason": "x"})
    assert r.status_code == 409


# ── bulk ───────────────────────────────────────────────────────────


async def test_bulk_approve(client: AsyncClient, seeded, mars_override):
    _, _, sugg = seeded
    pending_ids = [str(s.id) for s in sugg if s.status == "pending"]

    r = await client.post(
        f"{PREFIX}/suggestions/bulk",
        json={"suggestion_ids": pending_ids, "action": "approve"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["processed"] == 2
    assert body["total_requested"] == 2
    assert body["failed"] == []


async def test_bulk_approve_min_confidence(client: AsyncClient, seeded, mars_override):
    _, _, sugg = seeded
    pending_ids = [str(s.id) for s in sugg if s.status == "pending"]

    r = await client.post(
        f"{PREFIX}/suggestions/bulk",
        json={
            "suggestion_ids": pending_ids,
            "action": "approve",
            "min_confidence": 0.7,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["processed"] == 1  # only the 0.9 confidence one
    assert len(body["failed"]) == 1
    assert body["failed"][0]["reason"] == "below_confidence_threshold"


async def test_bulk_reject_with_reason(client: AsyncClient, seeded, mars_override):
    _, _, sugg = seeded
    pending_ids = [str(s.id) for s in sugg if s.status == "pending"]

    r = await client.post(
        f"{PREFIX}/suggestions/bulk",
        json={
            "suggestion_ids": pending_ids,
            "action": "reject",
            "reason": "Non pertinente",
        },
    )
    assert r.status_code == 200
    assert r.json()["processed"] == 2


async def test_bulk_invalid_action_returns_422(client: AsyncClient, seeded, mars_override):
    _, _, sugg = seeded
    pending_ids = [str(s.id) for s in sugg if s.status == "pending"]

    r = await client.post(
        f"{PREFIX}/suggestions/bulk",
        json={"suggestion_ids": pending_ids, "action": "delete"},
    )
    assert r.status_code == 422  # Pydantic Literal rejects
