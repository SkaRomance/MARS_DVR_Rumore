from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_200(client: AsyncClient):
    response = await client.get("/health/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_check_response_structure(client: AsyncClient):
    response = await client.get("/health/")
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "timestamp" in data
    assert "db_status" in data
    assert "redis_status" in data
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0


@pytest.mark.asyncio
async def test_health_check_timestamp_is_utc(client: AsyncClient):
    response = await client.get("/health/")
    data = response.json()
    ts = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    now = datetime.now(UTC)
    delta = abs((now - ts).total_seconds())
    assert delta < 10


@pytest.mark.asyncio
async def test_health_check_healthy_with_mocked_redis(client: AsyncClient):
    with (
        patch("src.api.routes.health.check_db", return_value="ok"),
        patch("src.api.routes.health.check_redis", return_value="ok"),
    ):
        response = await client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["db_status"] == "ok"
        assert data["redis_status"] == "ok"


@pytest.mark.asyncio
async def test_health_check_db_down(client: AsyncClient):
    with (
        patch("src.api.routes.health.check_db", return_value="error"),
        patch("src.api.routes.health.check_redis", return_value="ok"),
    ):
        response = await client.get("/health/")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["db_status"] == "error"
        assert data["redis_status"] == "ok"


@pytest.mark.asyncio
async def test_health_check_redis_down(client: AsyncClient):
    with (
        patch("src.api.routes.health.check_db", return_value="ok"),
        patch("src.api.routes.health.check_redis", return_value="unavailable"),
    ):
        response = await client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["db_status"] == "ok"
        assert data["redis_status"] == "unavailable"
