import uuid

import pytest
from httpx import AsyncClient

EXPORT_PREFIX = "/api/v1/noise/export"


@pytest.mark.asyncio
async def test_list_templates_no_auth(client: AsyncClient):
    response = await client.get(f"{EXPORT_PREFIX}/templates")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_print_settings_no_auth(client: AsyncClient):
    response = await client.get(f"{EXPORT_PREFIX}/print-settings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_json_no_auth(client: AsyncClient):
    random_uuid = str(uuid.uuid4())
    response = await client.post(
        f"{EXPORT_PREFIX}/assessments/{random_uuid}/json",
        json={"format": "json", "language": "it"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_docx_no_auth(client: AsyncClient):
    random_uuid = str(uuid.uuid4())
    response = await client.post(
        f"{EXPORT_PREFIX}/assessments/{random_uuid}/docx",
        json={"format": "dvr_full", "language": "it"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_preview_no_auth(client: AsyncClient):
    random_uuid = str(uuid.uuid4())
    response = await client.get(
        f"{EXPORT_PREFIX}/assessments/{random_uuid}/preview",
    )
    assert response.status_code == 401
