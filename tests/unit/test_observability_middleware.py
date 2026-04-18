"""Tests for the correlation-id middleware."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.infrastructure.observability.middleware import (
    REQUEST_ID_HEADER,
    CorrelationIdMiddleware,
)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    return app


@pytest.mark.asyncio
async def test_generates_request_id_when_missing():
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/ping")
    assert response.status_code == 200
    request_id = response.headers[REQUEST_ID_HEADER]
    # Must be a valid UUID.
    uuid.UUID(request_id)


@pytest.mark.asyncio
async def test_reuses_incoming_request_id():
    app = _build_app()
    incoming_id = "fixed-request-id-123"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/ping", headers={REQUEST_ID_HEADER: incoming_id})
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == incoming_id


@pytest.mark.asyncio
async def test_request_ids_differ_across_requests():
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        first = await ac.get("/ping")
        second = await ac.get("/ping")
    assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]
