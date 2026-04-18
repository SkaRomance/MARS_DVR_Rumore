"""End-to-end tests for observability wiring (Prometheus + correlation id)."""

import pytest
from httpx import AsyncClient

from src.infrastructure.observability.middleware import REQUEST_ID_HEADER


@pytest.mark.asyncio
async def test_metrics_endpoint_exposed(client: AsyncClient):
    response = await client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    # prometheus_fastapi_instrumentator emits the standard HTTP family.
    assert "http_request" in body or "process_" in body


@pytest.mark.asyncio
async def test_correlation_id_header_on_every_response(client: AsyncClient):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.headers.get(REQUEST_ID_HEADER)


@pytest.mark.asyncio
async def test_correlation_id_is_echoed_back(client: AsyncClient):
    incoming_id = "test-correlation-42"
    response = await client.get(
        "/health/live",
        headers={REQUEST_ID_HEADER: incoming_id},
    )
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == incoming_id
