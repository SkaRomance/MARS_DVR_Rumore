import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.company import Company

ASSESSMENT_PREFIX = "/api/v1/noise"


@pytest_asyncio.fixture
async def test_company(db_session: AsyncSession, test_tenant):
    company = Company(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        name="Test Company S.r.l.",
        ateco_primary_code="25.11.00",
        status="active",
        version=1,
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company


@pytest.mark.asyncio
async def test_create_assessment(
    client: AsyncClient, test_admin_user, auth_headers, test_company
):
    response = await client.post(
        f"{ASSESSMENT_PREFIX}/",
        json={
            "company_id": str(test_company.id),
            "ateco_code": "25.11.00",
            "description": "Valutazione rischio rumore",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["company_id"] == str(test_company.id)
    assert data["status"] == "active"
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_list_assessments(
    client: AsyncClient, test_admin_user, auth_headers, test_company
):
    await client.post(
        f"{ASSESSMENT_PREFIX}/",
        json={
            "company_id": str(test_company.id),
            "ateco_code": "25.11.00",
        },
        headers=auth_headers,
    )
    response = await client.get(f"{ASSESSMENT_PREFIX}/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_assessment_not_found(client: AsyncClient, auth_headers):
    random_uuid = str(uuid.uuid4())
    response = await client.get(
        f"{ASSESSMENT_PREFIX}/{random_uuid}", headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_assessment_no_auth(client: AsyncClient, test_company):
    response = await client.post(
        f"{ASSESSMENT_PREFIX}/",
        json={
            "company_id": str(test_company.id),
            "ateco_code": "25.11.00",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_calculate_exposure(client: AsyncClient, test_admin_user, auth_headers):
    assessment_id = str(uuid.uuid4())
    response = await client.post(
        f"{ASSESSMENT_PREFIX}/calculate",
        json={
            "assessment_id": assessment_id,
            "exposures": [
                {
                    "laeq_db_a": 85.0,
                    "duration_hours": 8.0,
                    "origin": "measured",
                }
            ],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "lex_8h" in data
    assert isinstance(data["lex_8h"], float)


@pytest.mark.asyncio
async def test_delete_assessment_not_found(client: AsyncClient, auth_headers):
    random_uuid = str(uuid.uuid4())
    response = await client.delete(
        f"{ASSESSMENT_PREFIX}/{random_uuid}", headers=auth_headers
    )
    assert response.status_code == 404
