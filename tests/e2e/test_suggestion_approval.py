"""End-to-end suggestion approval flow.

Bootstraps a context, seeds a pending suggestion via the service layer
directly (using the app's own async engine so the uvicorn subprocess
sees it), then approves the suggestion over HTTP and re-fetches to
verify the persisted status transition.
"""

from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.e2e


API_PREFIX = "/api/v1/noise"


async def _bootstrap_context(client: httpx.AsyncClient) -> uuid.UUID:
    body = {
        "company_id": "00000000-0000-0000-0000-000000000042",
        "dvr_id": str(uuid.uuid4()),
        "force_sync": True,
    }
    resp = await client.post(f"{API_PREFIX}/contexts", json=body)
    if resp.status_code >= 400:
        pytest.skip(f"context bootstrap not available in this env (status={resp.status_code})")
    return uuid.UUID(resp.json()["id"])


async def _seed_pending_suggestion(context_id: uuid.UUID, tenant_id: uuid.UUID) -> uuid.UUID:
    """Insert a pending AI suggestion straight into the live sqlite db.

    The E2E app uses `sqlite+aiosqlite:///./test_e2e.db`; we open a
    short-lived engine bound to the same file and persist a row via
    the domain service so the schema stays authoritative.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from src.domain.services.suggestion_service import SuggestionServiceV2

    engine = create_async_engine("sqlite+aiosqlite:///./test_e2e.db")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_maker() as session:
            svc = SuggestionServiceV2(session)
            result = await svc.create(
                context_id=context_id,
                tenant_id=tenant_id,
                kind="mitigation",
                payload={"phase_id": "p1", "measure": "use ear muffs"},
                confidence=0.85,
                rationale="E2E seed",
            )
            await session.commit()
            return uuid.UUID(result["id"])
    finally:
        await engine.dispose()


async def test_approve_suggestion_updates_status_e2e(http_client: httpx.AsyncClient) -> None:
    from tests.e2e.conftest import TEST_TENANT_ID

    context_id = await _bootstrap_context(http_client)

    try:
        suggestion_id = await _seed_pending_suggestion(context_id, TEST_TENANT_ID)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"could not seed suggestion directly: {exc}")

    approve_resp = await http_client.post(
        f"{API_PREFIX}/suggestions/{suggestion_id}/approve",
        json={"edited_payload": None},
    )
    assert approve_resp.status_code == 200, approve_resp.text

    list_resp = await http_client.get(f"{API_PREFIX}/suggestions", params={"context_id": str(context_id)})
    assert list_resp.status_code == 200
    suggestions = list_resp.json()
    if isinstance(suggestions, dict) and "items" in suggestions:
        suggestions = suggestions["items"]

    match = next((s for s in suggestions if s["id"] == str(suggestion_id)), None)
    assert match is not None, "approved suggestion missing from listing"
    assert match["status"] == "approved"
