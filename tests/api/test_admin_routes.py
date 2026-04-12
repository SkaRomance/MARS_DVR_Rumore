from io import BytesIO

import pytest
from httpx import AsyncClient

ADMIN_PREFIX = "/api/v1/noise/admin"


@pytest.mark.asyncio
async def test_get_tenant_info(client: AsyncClient, auth_headers, test_tenant):
    response = await client.get(f"{ADMIN_PREFIX}/tenant", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_tenant.name


@pytest.mark.asyncio
async def test_get_tenant_no_auth(client: AsyncClient):
    response = await client.get(f"{ADMIN_PREFIX}/tenant")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_logo_admin(client: AsyncClient, auth_headers):
    files = {"upload": ("logo.png", BytesIO(b"fake_png_data"), "image/png")}
    data = {"content_type": "image/png"}
    response = await client.post(
        f"{ADMIN_PREFIX}/tenant/logo",
        files=files,
        data=data,
        headers=auth_headers,
    )
    assert response.status_code == 200
    resp_data = response.json()
    assert "message" in resp_data


@pytest.mark.asyncio
async def test_get_logo(client: AsyncClient, auth_headers):
    response = await client.get(f"{ADMIN_PREFIX}/tenant/logo", headers=auth_headers)
    assert response.status_code in (200, 404)


@pytest.mark.asyncio
async def test_delete_logo_admin(client: AsyncClient, auth_headers):
    response = await client.delete(f"{ADMIN_PREFIX}/tenant/logo", headers=auth_headers)
    assert response.status_code == 200
