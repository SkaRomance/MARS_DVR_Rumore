"""API tests for /api/v1/noise/autopilot/* (SSE run + status + cancel)."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from httpx import AsyncClient

from src.api.dependencies.mars import get_mars_client, require_mars_context
from src.api.routes.autopilot_routes import get_llm_provider
from src.bootstrap.main import app
from src.infrastructure.database.models.ai_suggestion import AISuggestion
from src.infrastructure.database.models.noise_assessment_context import (
    NoiseAssessmentContext,
)
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.llm.mock_provider import MockProvider
from src.infrastructure.mars.client import MarsApiClient
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


def _dvr_snapshot(n_phases=2) -> dict:
    return {
        "schemaVersion": "1.1.0",
        "companyData": {"vatNumber": "IT0", "legalName": "ACME"},
        "workPhases": [{"id": f"ph-{i}", "name": f"P{i}", "description": ""} for i in range(1, n_phases + 1)],
        "phaseEquipments": [],
        "risks": [],
        "actions": [],
        "trainings": [],
        "module_extensions": {},
    }


@pytest.fixture
async def seeded(db_session):
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
        dvr_snapshot=_dvr_snapshot(2),
        dvr_schema_version="1.1.0",
        status="bootstrapped",
    )
    db_session.add(ctx)
    await db_session.flush()
    return tenant, ctx


@pytest.fixture
def mars_override(seeded):
    tenant, _ctx = seeded
    mars_ctx = MarsContext(
        user_id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="hse@example.com",
        enabled_modules=["noise"],
        access_token="bearer-test",
    )
    app.dependency_overrides[require_mars_context] = lambda: mars_ctx
    client = MarsApiClient(
        base_url="http://mars.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        max_retries=0,
    )
    app.dependency_overrides[get_mars_client] = lambda: client
    yield mars_ctx
    app.dependency_overrides.pop(require_mars_context, None)
    app.dependency_overrides.pop(get_mars_client, None)


@pytest.fixture
def llm_override():
    def _set(estimates: list[dict]):
        provider = MockProvider(response_content=json.dumps({"estimates": estimates}))
        app.dependency_overrides[get_llm_provider] = lambda: provider
        return provider

    yield _set
    app.dependency_overrides.pop(get_llm_provider, None)


def _parse_sse_frames(body: str) -> list[dict]:
    """Parse 'data: {...}\\n\\n' frames into dicts."""
    frames: list[dict] = []
    for chunk in body.split("\n\n"):
        chunk = chunk.strip()
        if not chunk.startswith("data: "):
            continue
        try:
            frames.append(json.loads(chunk[6:]))
        except json.JSONDecodeError:
            continue
    return frames


# ── POST /run ─────────────────────────────────────────────────────


async def test_run_streams_events_to_completion(client: AsyncClient, seeded, mars_override, llm_override):
    _, ctx = seeded
    llm_override(
        [
            {
                "phase_id": "ph-1",
                "phase_name": "P1",
                "laeq_db": 85.0,
                "duration_hours": 4.0,
                "k_tone_db": 0,
                "k_imp_db": 0,
                "confidence": 0.8,
                "reasoning": "ok",
                "data_gaps": [],
            },
            {
                "phase_id": "ph-2",
                "phase_name": "P2",
                "laeq_db": 90.0,
                "duration_hours": 2.0,
                "k_tone_db": 0,
                "k_imp_db": 0,
                "confidence": 0.7,
                "reasoning": "ok",
                "data_gaps": [],
            },
        ]
    )

    r = await client.post(f"{PREFIX}/autopilot/{ctx.id}/run")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")

    frames = _parse_sse_frames(r.text)
    kinds = [f["kind"] for f in frames]
    assert "started" in kinds
    assert "completed" in kinds
    final = frames[-1]
    assert final["kind"] == "completed"
    assert final["payload"]["lex_8h_db"] > 0
    assert final["payload"]["risk_band"] in {"green", "yellow", "orange", "red"}
    assert final["payload"]["suggestions_count"] == 2


async def test_run_empty_snapshot_still_completes(client: AsyncClient, db_session, mars_override, llm_override):
    # Seed a context WITH snapshot but zero phases
    tenant = Tenant(id=uuid.uuid4(), name="T", slug=f"t-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    ctx = NoiseAssessmentContext(
        id=uuid.uuid4(),
        tenant_id=mars_override.tenant_id,  # same tenant as override
        user_id=uuid.uuid4(),
        mars_dvr_document_id=uuid.uuid4(),
        mars_revision_id=uuid.uuid4(),
        mars_document_version=1,
        dvr_snapshot=_dvr_snapshot(0),
        dvr_schema_version="1.1.0",
        status="bootstrapped",
    )
    db_session.add(ctx)
    await db_session.flush()

    llm_override([])
    r = await client.post(f"{PREFIX}/autopilot/{ctx.id}/run")
    assert r.status_code == 200
    frames = _parse_sse_frames(r.text)
    final = frames[-1]
    assert final["kind"] == "completed"
    assert final["payload"]["lex_8h_db"] == 0
    assert final["payload"]["risk_band"] == "green"


async def test_run_missing_snapshot_returns_409(client: AsyncClient, db_session, mars_override, llm_override):
    ctx = NoiseAssessmentContext(
        id=uuid.uuid4(),
        tenant_id=mars_override.tenant_id,
        user_id=uuid.uuid4(),
        mars_dvr_document_id=uuid.uuid4(),
        mars_revision_id=uuid.uuid4(),
        mars_document_version=1,
        dvr_snapshot=None,  # explicit
        status="bootstrapped",
    )
    db_session.add(ctx)
    await db_session.flush()

    llm_override([])
    r = await client.post(f"{PREFIX}/autopilot/{ctx.id}/run")
    assert r.status_code == 409
    assert "snapshot" in r.json()["detail"].lower()


async def test_run_unknown_context_returns_404(client: AsyncClient, mars_override, llm_override):
    llm_override([])
    r = await client.post(f"{PREFIX}/autopilot/{uuid.uuid4()}/run")
    assert r.status_code == 404


async def test_run_cross_tenant_returns_404(client: AsyncClient, db_session, seeded, llm_override):
    """Caller from tenant A tries to run autopilot on tenant B's context."""
    _, ctx = seeded
    # Set override to a DIFFERENT tenant
    other_tenant = Tenant(id=uuid.uuid4(), name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    db_session.add(other_tenant)
    await db_session.flush()

    mars_ctx = MarsContext(
        user_id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        access_token="bearer-test",
        enabled_modules=["noise"],
    )
    app.dependency_overrides[require_mars_context] = lambda: mars_ctx

    llm_override([])
    try:
        r = await client.post(f"{PREFIX}/autopilot/{ctx.id}/run")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(require_mars_context, None)


async def test_run_no_auth_returns_401(client: AsyncClient, seeded, llm_override):
    _, ctx = seeded
    llm_override([])
    r = await client.post(f"{PREFIX}/autopilot/{ctx.id}/run")
    assert r.status_code == 401


# ── GET /status ────────────────────────────────────────────────────


async def test_status_returns_current_state(client: AsyncClient, seeded, mars_override):
    _, ctx = seeded
    r = await client.get(f"{PREFIX}/autopilot/{ctx.id}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["context_id"] == str(ctx.id)
    assert body["has_snapshot"] is True
    assert body["is_running"] is False
    assert body["suggestions_count"] == 0


async def test_status_counts_pending_suggestions(client: AsyncClient, db_session, seeded, mars_override):
    tenant, ctx = seeded
    # Seed 3 suggestions: 2 pending + 1 approved

    for status_val in ("pending", "pending", "approved"):
        db_session.add(
            AISuggestion(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                context_id=ctx.id,
                suggestion_type="phase_laeq",
                title="t",
                content={},
                status=status_val,
            )
        )
    await db_session.flush()

    r = await client.get(f"{PREFIX}/autopilot/{ctx.id}/status")
    body = r.json()
    assert body["suggestions_count"] == 3
    assert body["pending_count"] == 2


async def test_status_unknown_context_returns_404(client: AsyncClient, mars_override):
    r = await client.get(f"{PREFIX}/autopilot/{uuid.uuid4()}/status")
    assert r.status_code == 404


# ── POST /cancel ───────────────────────────────────────────────────


async def test_cancel_when_not_running_returns_noop(client: AsyncClient, seeded, mars_override):
    _, ctx = seeded
    r = await client.post(f"{PREFIX}/autopilot/{ctx.id}/cancel")
    assert r.status_code == 200
    assert r.json()["cancelled"] is False
    assert r.json()["reason"] == "no_active_run"
