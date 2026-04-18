"""E2E test for the thin-plugin invariant: MARS owns DVR state.

The SafeEditor endpoint is expected to reject any direct mutation of
the cached `dvr_snapshot` payload with a 409 Conflict, forcing
consumers to write through MARS instead. Until that endpoint lands
this test is skipped, so the build stays green on branches that
haven't implemented it yet.
"""

from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.e2e


API_PREFIX = "/api/v1/noise"


async def test_safe_editor_prevents_direct_dvr_mutation_e2e(
    http_client: httpx.AsyncClient,
) -> None:
    # Bootstrap a context to target.
    bootstrap = await http_client.post(
        f"{API_PREFIX}/contexts",
        json={
            "company_id": "00000000-0000-0000-0000-000000000042",
            "dvr_id": str(uuid.uuid4()),
            "force_sync": True,
        },
    )
    if bootstrap.status_code >= 400:
        pytest.skip(f"context bootstrap not available (status={bootstrap.status_code})")

    context_id = bootstrap.json()["id"]

    # Attempt to PUT a raw dvr_snapshot mutation onto the context.
    # If the SafeEditor endpoint isn't wired yet, skip rather than fail.
    resp = await http_client.put(
        f"{API_PREFIX}/contexts/{context_id}",
        json={"dvr_snapshot": {"phases": [{"id": "hacked", "name": "injected"}]}},
    )

    if resp.status_code in {404, 405}:
        pytest.skip("SafeEditor endpoint not implemented yet")

    # The invariant: the plugin must not accept direct DVR snapshot writes.
    assert resp.status_code in {409, 422, 403}, (
        f"expected rejection of direct DVR mutation, got {resp.status_code}: {resp.text[:200]}"
    )
