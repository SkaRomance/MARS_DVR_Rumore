"""Integration tests for /api/v1/noise/contexts/* endpoints.

Uses the conftest `client` fixture (AsyncClient wired to the real app
with SQLite + DB override) + FastAPI dep overrides for MARS layer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from httpx import AsyncClient

from src.api.dependencies.mars import get_mars_client, require_mars_context
from src.bootstrap.main import app
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.mars.client import MarsApiClient
from src.infrastructure.mars.types import MarsContext

PREFIX = "/api/v1/noise"


@pytest.fixture(autouse=True)
def _configure_mars_for_tests(monkeypatch):
    """Ensure MARS validator singleton can build without real JWKS config.

    Without this, FastAPI tries to build MarsJwtValidator(RS256) as part
    of dep resolution for require_mars_context, fails with ValueError,
    and we never reach the auth-check path. For tests that override the
    dep anyway, the validator is never called — we just need it to
    construct successfully.
    """
    from src.api.dependencies.mars import reset_mars_singletons
    from src.bootstrap.config import get_settings

    monkeypatch.setenv("MARS_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("MARS_JWT_HS256_SECRET", "x" * 32)
    get_settings.cache_clear()
    reset_mars_singletons()
    yield
    get_settings.cache_clear()
    reset_mars_singletons()


def _make_mars_client(body: dict) -> MarsApiClient:
    def handler(request):
        return httpx.Response(200, json=body)

    return MarsApiClient(
        base_url="http://mars.test",
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )


def _revision_body(doc_id: uuid.UUID, rev_id: uuid.UUID, version: int = 1) -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "id": str(rev_id),
        "documentId": str(doc_id),
        "tenantId": str(uuid.uuid4()),
        "version": version,
        "status": "draft",
        "snapshot": {
            "schemaVersion": "1.1.0",
            "companyData": {"vatNumber": "IT12345678901", "legalName": "ACME"},
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


@pytest.fixture
async def seeded_tenant(db_session):
    t = Tenant(id=uuid.uuid4(), name="Test", slug=f"t-{uuid.uuid4().hex[:8]}")
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.fixture
async def override_mars(seeded_tenant):
    """Install MARS deps overrides; yields a setter + cleans up afterward."""
    clients_to_close: list[MarsApiClient] = []

    def _override(body: dict, user_id: uuid.UUID | None = None, modules=("noise",)):
        mars_ctx = MarsContext(
            user_id=user_id or uuid.uuid4(),
            tenant_id=seeded_tenant.id,
            email="u@e.com",
            enabled_modules=list(modules),
            access_token="bearer-test",
        )
        client = _make_mars_client(body)
        clients_to_close.append(client)

        app.dependency_overrides[require_mars_context] = lambda: mars_ctx
        app.dependency_overrides[get_mars_client] = lambda: client
        return mars_ctx

    yield _override

    app.dependency_overrides.pop(require_mars_context, None)
    app.dependency_overrides.pop(get_mars_client, None)
    for c in clients_to_close:
        await c.close()


# ── bootstrap ──────────────────────────────────────────────────────


async def test_bootstrap_creates_new_context(client: AsyncClient, override_mars, seeded_tenant):
    doc_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    override_mars(_revision_body(doc_id, rev_id))

    r = await client.post(
        f"{PREFIX}/contexts/bootstrap",
        json={
            "mars_dvr_document_id": str(doc_id),
            "mars_revision_id": str(rev_id),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert uuid.UUID(body["tenant_id"]) == seeded_tenant.id
    assert uuid.UUID(body["mars_dvr_document_id"]) == doc_id
    assert uuid.UUID(body["mars_revision_id"]) == rev_id
    assert body["status"] == "bootstrapped"
    assert body["dvr_schema_version"] == "1.1.0"


async def test_bootstrap_returns_same_row_on_repeat(client: AsyncClient, override_mars):
    doc_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    override_mars(_revision_body(doc_id, rev_id))

    a = await client.post(
        f"{PREFIX}/contexts/bootstrap",
        json={"mars_dvr_document_id": str(doc_id), "mars_revision_id": str(rev_id)},
    )
    b = await client.post(
        f"{PREFIX}/contexts/bootstrap",
        json={"mars_dvr_document_id": str(doc_id), "mars_revision_id": str(rev_id)},
    )
    assert a.status_code == 200
    assert b.status_code == 200
    assert a.json()["id"] == b.json()["id"]  # Same context row


async def test_bootstrap_without_auth_returns_401(client: AsyncClient):
    # No override → default require_mars_context fires → 401
    r = await client.post(
        f"{PREFIX}/contexts/bootstrap",
        json={"mars_dvr_document_id": str(uuid.uuid4())},
    )
    assert r.status_code == 401


# ── get / list / patch ─────────────────────────────────────────────


async def test_get_context_by_id(client: AsyncClient, override_mars):
    doc_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    override_mars(_revision_body(doc_id, rev_id))

    created = await client.post(
        f"{PREFIX}/contexts/bootstrap",
        json={"mars_dvr_document_id": str(doc_id), "mars_revision_id": str(rev_id)},
    )
    ctx_id = created.json()["id"]

    r = await client.get(f"{PREFIX}/contexts/{ctx_id}")
    assert r.status_code == 200
    assert r.json()["id"] == ctx_id


async def test_get_context_cross_tenant_is_404(client: AsyncClient, override_mars, seeded_tenant, db_session):
    """A context belonging to tenant X returns 404 when queried by tenant Y."""
    from src.infrastructure.database.models.noise_assessment_context import (
        NoiseAssessmentContext,
    )

    # Create a context in a DIFFERENT tenant directly via DB
    other = Tenant(id=uuid.uuid4(), name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    db_session.add(other)
    await db_session.flush()
    stranger_ctx = NoiseAssessmentContext(
        id=uuid.uuid4(),
        tenant_id=other.id,
        user_id=uuid.uuid4(),
        mars_dvr_document_id=uuid.uuid4(),
        mars_revision_id=uuid.uuid4(),
        mars_document_version=1,
        status="bootstrapped",
    )
    db_session.add(stranger_ctx)
    await db_session.flush()

    # Override auth as seeded_tenant (not `other`)
    override_mars({})

    r = await client.get(f"{PREFIX}/contexts/{stranger_ctx.id}")
    assert r.status_code == 404


async def test_get_context_by_dvr(client: AsyncClient, override_mars):
    doc_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    override_mars(_revision_body(doc_id, rev_id))

    await client.post(
        f"{PREFIX}/contexts/bootstrap",
        json={"mars_dvr_document_id": str(doc_id), "mars_revision_id": str(rev_id)},
    )

    r = await client.get(f"{PREFIX}/contexts/by-dvr/{doc_id}")
    assert r.status_code == 200
    assert uuid.UUID(r.json()["mars_dvr_document_id"]) == doc_id


async def test_list_contexts(client: AsyncClient, override_mars, seeded_tenant, db_session):
    """Pre-seed contexts directly via DB, then list via API."""
    from src.infrastructure.database.models.noise_assessment_context import (
        NoiseAssessmentContext,
    )

    for _ in range(3):
        db_session.add(
            NoiseAssessmentContext(
                id=uuid.uuid4(),
                tenant_id=seeded_tenant.id,
                user_id=uuid.uuid4(),
                mars_dvr_document_id=uuid.uuid4(),
                mars_revision_id=uuid.uuid4(),
                mars_document_version=1,
                dvr_schema_version="1.1.0",
                status="bootstrapped",
            )
        )
    await db_session.flush()

    override_mars({})  # seeded_tenant is the auth tenant

    r = await client.get(f"{PREFIX}/contexts/")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert all(c["dvr_schema_version"] == "1.1.0" for c in body["items"])


async def test_update_context_status(client: AsyncClient, override_mars):
    doc_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    override_mars(_revision_body(doc_id, rev_id))

    created = await client.post(
        f"{PREFIX}/contexts/bootstrap",
        json={"mars_dvr_document_id": str(doc_id), "mars_revision_id": str(rev_id)},
    )
    ctx_id = created.json()["id"]

    r = await client.patch(
        f"{PREFIX}/contexts/{ctx_id}/status",
        json={"status": "in_progress"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"


async def test_update_status_invalid_returns_422(client: AsyncClient, override_mars):
    doc_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    override_mars(_revision_body(doc_id, rev_id))

    created = await client.post(
        f"{PREFIX}/contexts/bootstrap",
        json={"mars_dvr_document_id": str(doc_id), "mars_revision_id": str(rev_id)},
    )
    ctx_id = created.json()["id"]

    r = await client.patch(
        f"{PREFIX}/contexts/{ctx_id}/status",
        json={"status": "not-a-status"},
    )
    assert r.status_code == 422


async def test_get_context_by_dvr_404_when_missing(client: AsyncClient, override_mars):
    override_mars({})
    r = await client.get(f"{PREFIX}/contexts/by-dvr/{uuid.uuid4()}")
    assert r.status_code == 404
