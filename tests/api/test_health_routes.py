from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from src.api.routes import health as health_module


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


# ---------------------------------------------------------------------------
# Kubernetes-style probes: /health/live, /health/ready, /health/startup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_liveness_probe_always_returns_200(client: AsyncClient):
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_liveness_probe_does_not_touch_db(client: AsyncClient):
    """Liveness must be lightweight — never hit the DB."""
    with patch("src.api.routes.health.check_db") as db_check:
        response = await client.get("/health/live")
    assert response.status_code == 200
    db_check.assert_not_called()


@pytest.mark.asyncio
async def test_readiness_probe_ok_when_all_healthy(client: AsyncClient):
    with (
        patch("src.api.routes.health.check_db", return_value="ok"),
        patch("src.api.routes.health.check_redis", return_value="ok"),
    ):
        response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["db_status"] == "ok"
    assert data["redis_status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_probe_degraded_when_redis_unavailable(client: AsyncClient):
    with (
        patch("src.api.routes.health.check_db", return_value="ok"),
        patch("src.api.routes.health.check_redis", return_value="unavailable"),
    ):
        response = await client.get("/health/ready")
    # Redis missing is soft-fail — still 200 so we stay in rotation.
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["redis_status"] == "unavailable"


@pytest.mark.asyncio
async def test_readiness_probe_503_when_db_down(client: AsyncClient):
    with (
        patch("src.api.routes.health.check_db", return_value="error"),
        patch("src.api.routes.health.check_redis", return_value="ok"),
    ):
        response = await client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["db_status"] == "error"


@pytest.mark.asyncio
async def test_startup_probe_503_until_marked_complete(client: AsyncClient):
    health_module.reset_startup_complete()
    try:
        response = await client.get("/health/startup")
        assert response.status_code == 503
        assert response.json()["status"] == "starting"
    finally:
        health_module.reset_startup_complete()


@pytest.mark.asyncio
async def test_startup_probe_200_after_marked_complete(client: AsyncClient):
    health_module.mark_startup_complete()
    try:
        response = await client.get("/health/startup")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "version" in data
    finally:
        health_module.reset_startup_complete()
