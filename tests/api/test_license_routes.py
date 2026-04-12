from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from src.bootstrap.main import app
from src.api.routes.license_routes import _get_license_service
from src.infrastructure.licensing.license_service import LicenseService

LICENSE_PREFIX = "/api/v1/noise/license"


@pytest.mark.asyncio
async def test_get_license_status(
    client: AsyncClient, auth_headers, test_tenant, db_session
):
    mock_service = AsyncMock(spec=LicenseService)
    mock_service.get_license_status.return_value = {
        "status": "inactive",
        "plan": "free",
        "license_key_masked": None,
        "activated_at": None,
        "expires_at": None,
        "features": [],
    }

    async def override_license_service():
        return mock_service

    app.dependency_overrides[_get_license_service] = override_license_service

    try:
        response = await client.get(f"{LICENSE_PREFIX}/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["license_status"] == "inactive"
        assert data["plan"] == "free"
        mock_service.get_license_status.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(_get_license_service, None)


@pytest.mark.asyncio
async def test_activate_license_as_admin(
    client: AsyncClient, auth_headers, test_tenant, db_session
):
    mock_service = AsyncMock(spec=LicenseService)
    mock_service.activate_license.return_value = {
        "status": "active",
        "plan": "professional",
        "features": ["max_assessments_100"],
        "expires_at": "2026-12-31T23:59:59Z",
    }
    mock_service.get_license_status.return_value = {
        "status": "active",
        "plan": "professional",
        "license_key_masked": "key-****-abcd",
        "activated_at": "2025-01-01T00:00:00Z",
        "expires_at": "2026-12-31T23:59:59Z",
        "features": ["max_assessments_100"],
    }

    async def override_license_service():
        return mock_service

    app.dependency_overrides[_get_license_service] = override_license_service

    try:
        response = await client.post(
            f"{LICENSE_PREFIX}/activate",
            headers=auth_headers,
            json={"license_key": "test-license-key", "machine_fingerprint": "fp-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["license_status"] == "active"
        assert data["plan"] == "professional"
        mock_service.activate_license.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(_get_license_service, None)


@pytest.mark.asyncio
async def test_activate_license_failure(
    client: AsyncClient, auth_headers, test_tenant, db_session
):
    mock_service = AsyncMock(spec=LicenseService)
    mock_service.activate_license.return_value = {
        "status": "error",
        "detail": "License validation failed",
    }

    async def override_license_service():
        return mock_service

    app.dependency_overrides[_get_license_service] = override_license_service

    try:
        response = await client.post(
            f"{LICENSE_PREFIX}/activate",
            headers=auth_headers,
            json={"license_key": "bad-key", "machine_fingerprint": "fp-123"},
        )

        assert response.status_code == 400
        assert "failed" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(_get_license_service, None)


@pytest.mark.asyncio
async def test_deactivate_license_as_admin(
    client: AsyncClient, auth_headers, test_tenant, db_session
):
    mock_service = AsyncMock(spec=LicenseService)
    mock_service.deactivate_license.return_value = {"status": "inactive"}

    async def override_license_service():
        return mock_service

    app.dependency_overrides[_get_license_service] = override_license_service

    try:
        response = await client.post(
            f"{LICENSE_PREFIX}/deactivate",
            headers=auth_headers,
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deactivated"
        mock_service.deactivate_license.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(_get_license_service, None)


@pytest.mark.asyncio
async def test_deactivate_license_failure(
    client: AsyncClient, auth_headers, test_tenant, db_session
):
    mock_service = AsyncMock(spec=LicenseService)
    mock_service.deactivate_license.return_value = {
        "status": "error",
        "detail": "Deactivation failed",
    }

    async def override_license_service():
        return mock_service

    app.dependency_overrides[_get_license_service] = override_license_service

    try:
        response = await client.post(
            f"{LICENSE_PREFIX}/deactivate",
            headers=auth_headers,
            json={},
        )

        assert response.status_code == 400
    finally:
        app.dependency_overrides.pop(_get_license_service, None)


@pytest.mark.asyncio
async def test_get_usage(client: AsyncClient, auth_headers, test_tenant, db_session):
    mock_service = AsyncMock(spec=LicenseService)
    mock_service.get_usage.return_value = {
        "tenant_id": str(test_tenant.id),
        "plan": "free",
        "assessments_used": 3,
        "assessments_limit": 10,
        "features": [],
    }

    async def override_license_service():
        return mock_service

    app.dependency_overrides[_get_license_service] = override_license_service

    try:
        response = await client.get(f"{LICENSE_PREFIX}/usage", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "free"
        assert data["assessments_used"] == 3
        assert data["assessments_limit"] == 10
        mock_service.get_usage.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(_get_license_service, None)


@pytest.mark.asyncio
async def test_license_endpoints_require_auth(client: AsyncClient):
    response = await client.get(f"{LICENSE_PREFIX}/status")
    assert response.status_code == 401
