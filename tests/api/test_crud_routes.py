import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from src.infrastructure.auth.jwt_handler import create_access_token
from src.infrastructure.auth.password import get_password_hash
from src.infrastructure.database.enums import EntityStatus
from src.infrastructure.database.models.noise_assessment import NoiseAssessment
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User

COMPANIES_PREFIX = "/api/v1/noise/companies"
JOB_ROLES_PREFIX = "/api/v1/noise/job-roles"
MITIGATIONS_PREFIX = "/api/v1/noise/mitigations"
MACHINE_ASSETS_PREFIX = "/api/v1/noise/machine-assets"


@pytest.fixture
async def crud_tenant(db_session):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="CRUD Test Tenant",
        slug=f"crud-test-{uuid.uuid4().hex[:8]}",
        plan="free",
        license_status="inactive",
        max_assessments=10,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def crud_user(db_session, crud_tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=crud_tenant.id,
        email="crud@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="CRUD Tester",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def crud_auth_headers(crud_user):
    token = create_access_token(
        {
            "sub": str(crud_user.id),
            "tenant_id": str(crud_user.tenant_id),
            "role": crud_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def crud_company(client: AsyncClient, crud_auth_headers):
    response = await client.post(
        COMPANIES_PREFIX + "/",
        headers=crud_auth_headers,
        json={"name": "CRUD Corp Srl", "ateco_primary_code": "25.11.00"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def crud_assessment(db_session, crud_tenant, crud_company):
    assessment = NoiseAssessment(
        id=uuid.uuid4(),
        tenant_id=crud_tenant.id,
        company_id=uuid.UUID(crud_company["id"]),
        description="CRUD test assessment",
        status=EntityStatus.active.value,
        assessment_date=datetime.now(UTC),
        measurement_protocol="ISO 9612:2009",
        instrument_class="1",
        workers_count_exposed=3,
        version=1,
    )
    db_session.add(assessment)
    await db_session.commit()
    await db_session.refresh(assessment)
    return assessment


@pytest.fixture
async def other_tenant(db_session):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Other Tenant",
        slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
        plan="free",
        license_status="inactive",
        max_assessments=10,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def other_user(db_session, other_tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        email="other@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Other User",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_auth_headers(other_user):
    token = create_access_token(
        {
            "sub": str(other_user.id),
            "tenant_id": str(other_user.tenant_id),
            "role": other_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_company(client: AsyncClient, crud_auth_headers):
    response = await client.post(
        COMPANIES_PREFIX + "/",
        headers=crud_auth_headers,
        json={"name": "New Company", "ateco_primary_code": "25.11.00"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Company"
    assert data["ateco_primary_code"] == "25.11.00"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_companies(client: AsyncClient, crud_auth_headers, crud_company):
    response = await client.get(
        COMPANIES_PREFIX + "/",
        headers=crud_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(c["name"] == "CRUD Corp Srl" for c in data)


@pytest.mark.asyncio
async def test_get_company(client: AsyncClient, crud_auth_headers, crud_company):
    response = await client.get(
        f"{COMPANIES_PREFIX}/{crud_company['id']}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == crud_company["id"]
    assert data["name"] == "CRUD Corp Srl"


@pytest.mark.asyncio
async def test_get_company_not_found(client: AsyncClient, crud_auth_headers):
    random_uuid = str(uuid.uuid4())
    response = await client.get(
        f"{COMPANIES_PREFIX}/{random_uuid}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_company(client: AsyncClient, crud_auth_headers, crud_company):
    response = await client.put(
        f"{COMPANIES_PREFIX}/{crud_company['id']}",
        headers=crud_auth_headers,
        json={"name": "Updated Corp"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Corp"
    assert data["id"] == crud_company["id"]


@pytest.mark.asyncio
async def test_soft_delete_company(client: AsyncClient, crud_auth_headers, crud_company):
    response = await client.delete(
        f"{COMPANIES_PREFIX}/{crud_company['id']}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 204

    response = await client.get(
        f"{COMPANIES_PREFIX}/{crud_company['id']}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_company_unauthenticated(client: AsyncClient):
    response = await client.post(
        COMPANIES_PREFIX + "/",
        json={"name": "No Auth Company", "ateco_primary_code": "25.11.00"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_companies_unauthenticated(client: AsyncClient):
    response = await client.get(
        COMPANIES_PREFIX + "/",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_company_cross_tenant_access(client: AsyncClient, crud_auth_headers, other_auth_headers, crud_company):
    response = await client.get(
        f"{COMPANIES_PREFIX}/{crud_company['id']}",
        headers=other_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_job_role(client: AsyncClient, crud_auth_headers, crud_company):
    response = await client.post(
        JOB_ROLES_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "company_id": crud_company["id"],
            "name": "Operator",
            "description": "Machine operator role",
            "department": "Production",
            "exposure_level": "high",
            "risk_band": "medium",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Operator"
    assert data["company_id"] == crud_company["id"]
    assert data["department"] == "Production"


@pytest.mark.asyncio
async def test_list_job_roles(client: AsyncClient, crud_auth_headers, crud_company):
    create_resp = await client.post(
        JOB_ROLES_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "company_id": crud_company["id"],
            "name": "Supervisor",
        },
    )
    assert create_resp.status_code == 201

    response = await client.get(
        JOB_ROLES_PREFIX + "/",
        headers=crud_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_job_roles_filtered_by_company(client: AsyncClient, crud_auth_headers, crud_company):
    response = await client.get(
        JOB_ROLES_PREFIX + "/",
        headers=crud_auth_headers,
        params={"company_id": crud_company["id"]},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_job_role(client: AsyncClient, crud_auth_headers, crud_company):
    create_resp = await client.post(
        JOB_ROLES_PREFIX + "/",
        headers=crud_auth_headers,
        json={"company_id": crud_company["id"], "name": "Inspector"},
    )
    assert create_resp.status_code == 201
    job_role_id = create_resp.json()["id"]

    response = await client.get(
        f"{JOB_ROLES_PREFIX}/{job_role_id}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Inspector"


@pytest.mark.asyncio
async def test_get_job_role_not_found(client: AsyncClient, crud_auth_headers):
    response = await client.get(
        f"{JOB_ROLES_PREFIX}/{uuid.uuid4()}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_job_role(client: AsyncClient, crud_auth_headers, crud_company):
    create_resp = await client.post(
        JOB_ROLES_PREFIX + "/",
        headers=crud_auth_headers,
        json={"company_id": crud_company["id"], "name": "Technician"},
    )
    assert create_resp.status_code == 201
    job_role_id = create_resp.json()["id"]

    response = await client.put(
        f"{JOB_ROLES_PREFIX}/{job_role_id}",
        headers=crud_auth_headers,
        json={"name": "Senior Technician", "department": "Maintenance"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Senior Technician"
    assert data["department"] == "Maintenance"


@pytest.mark.asyncio
async def test_soft_delete_job_role(client: AsyncClient, crud_auth_headers, crud_company):
    create_resp = await client.post(
        JOB_ROLES_PREFIX + "/",
        headers=crud_auth_headers,
        json={"company_id": crud_company["id"], "name": "Deleter Role"},
    )
    assert create_resp.status_code == 201
    job_role_id = create_resp.json()["id"]

    response = await client.delete(
        f"{JOB_ROLES_PREFIX}/{job_role_id}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 204

    response = await client.get(
        f"{JOB_ROLES_PREFIX}/{job_role_id}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_job_role_unauthenticated(client: AsyncClient, crud_company):
    response = await client.post(
        JOB_ROLES_PREFIX + "/",
        json={"company_id": crud_company["id"], "name": "No Auth Role"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_job_role_cross_tenant(client: AsyncClient, crud_auth_headers, other_auth_headers, crud_company):
    create_resp = await client.post(
        JOB_ROLES_PREFIX + "/",
        headers=crud_auth_headers,
        json={"company_id": crud_company["id"], "name": "Cross Tenant Role"},
    )
    assert create_resp.status_code == 201
    job_role_id = create_resp.json()["id"]

    response = await client.get(
        f"{JOB_ROLES_PREFIX}/{job_role_id}",
        headers=other_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_mitigation(client: AsyncClient, crud_auth_headers, crud_assessment):
    response = await client.post(
        MITIGATIONS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "assessment_id": str(crud_assessment.id),
            "type": "engineering",
            "title": "Install sound enclosure",
            "description": "Enclose the noisy machine",
            "priority": 2,
            "status": "pending",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Install sound enclosure"
    assert data["type"] == "engineering"
    assert data["assessment_id"] == str(crud_assessment.id)


@pytest.mark.asyncio
async def test_list_mitigations(client: AsyncClient, crud_auth_headers, crud_assessment):
    await client.post(
        MITIGATIONS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "assessment_id": str(crud_assessment.id),
            "type": "ppe",
            "title": "Provide earplugs",
        },
    )

    response = await client.get(
        MITIGATIONS_PREFIX + "/",
        headers=crud_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_mitigations_filtered_by_assessment(client: AsyncClient, crud_auth_headers, crud_assessment):
    response = await client.get(
        MITIGATIONS_PREFIX + "/",
        headers=crud_auth_headers,
        params={"assessment_id": str(crud_assessment.id)},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_mitigation(client: AsyncClient, crud_auth_headers, crud_assessment):
    create_resp = await client.post(
        MITIGATIONS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "assessment_id": str(crud_assessment.id),
            "type": "administrative",
            "title": "Rotate shifts",
        },
    )
    assert create_resp.status_code == 201
    measure_id = create_resp.json()["id"]

    response = await client.get(
        f"{MITIGATIONS_PREFIX}/{measure_id}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Rotate shifts"


@pytest.mark.asyncio
async def test_get_mitigation_not_found(client: AsyncClient, crud_auth_headers):
    response = await client.get(
        f"{MITIGATIONS_PREFIX}/{uuid.uuid4()}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_mitigation(client: AsyncClient, crud_auth_headers, crud_assessment):
    create_resp = await client.post(
        MITIGATIONS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "assessment_id": str(crud_assessment.id),
            "type": "engineering",
            "title": "Original title",
        },
    )
    assert create_resp.status_code == 201
    measure_id = create_resp.json()["id"]

    response = await client.put(
        f"{MITIGATIONS_PREFIX}/{measure_id}",
        headers=crud_auth_headers,
        json={"title": "Updated title", "status": "completed"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated title"
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_soft_delete_mitigation(client: AsyncClient, crud_auth_headers, crud_assessment):
    create_resp = await client.post(
        MITIGATIONS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "assessment_id": str(crud_assessment.id),
            "type": "ppe",
            "title": "Delete me",
        },
    )
    assert create_resp.status_code == 201
    measure_id = create_resp.json()["id"]

    response = await client.delete(
        f"{MITIGATIONS_PREFIX}/{measure_id}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 204

    response = await client.get(
        f"{MITIGATIONS_PREFIX}/{measure_id}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mitigation_unauthenticated(client: AsyncClient, crud_assessment):
    response = await client.post(
        MITIGATIONS_PREFIX + "/",
        json={
            "assessment_id": str(crud_assessment.id),
            "type": "engineering",
            "title": "No auth mitigation",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mitigation_cross_tenant(client: AsyncClient, crud_auth_headers, other_auth_headers, crud_assessment):
    create_resp = await client.post(
        MITIGATIONS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "assessment_id": str(crud_assessment.id),
            "type": "engineering",
            "title": "Cross tenant mitigation",
        },
    )
    assert create_resp.status_code == 201
    measure_id = create_resp.json()["id"]

    response = await client.get(
        f"{MITIGATIONS_PREFIX}/{measure_id}",
        headers=other_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_machine_asset(client: AsyncClient, crud_auth_headers, crud_company):
    response = await client.post(
        MACHINE_ASSETS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "company_id": crud_company["id"],
            "marca": "Siemens",
            "modello": "XM-500",
            "matricola": "SN12345",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["marca"] == "Siemens"
    assert data["modello"] == "XM-500"
    assert data["company_id"] == crud_company["id"]


@pytest.mark.asyncio
async def test_list_machine_assets(client: AsyncClient, crud_auth_headers, crud_company):
    await client.post(
        MACHINE_ASSETS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "company_id": crud_company["id"],
            "marca": "Bosch",
            "modello": "RX-200",
        },
    )

    response = await client.get(
        MACHINE_ASSETS_PREFIX + "/",
        headers=crud_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_machine_assets_filtered_by_company(client: AsyncClient, crud_auth_headers, crud_company):
    response = await client.get(
        MACHINE_ASSETS_PREFIX + "/",
        headers=crud_auth_headers,
        params={"company_id": crud_company["id"]},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_machine_asset(client: AsyncClient, crud_auth_headers, crud_company):
    create_resp = await client.post(
        MACHINE_ASSETS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "company_id": crud_company["id"],
            "marca": "Festool",
            "modello": "TXT-100",
        },
    )
    assert create_resp.status_code == 201
    asset_id = create_resp.json()["id"]

    response = await client.get(
        f"{MACHINE_ASSETS_PREFIX}/{asset_id}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["marca"] == "Festool"


@pytest.mark.asyncio
async def test_get_machine_asset_not_found(client: AsyncClient, crud_auth_headers):
    response = await client.get(
        f"{MACHINE_ASSETS_PREFIX}/{uuid.uuid4()}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_machine_asset(client: AsyncClient, crud_auth_headers, crud_company):
    create_resp = await client.post(
        MACHINE_ASSETS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "company_id": crud_company["id"],
            "marca": "Makita",
            "modello": "HR-300",
        },
    )
    assert create_resp.status_code == 201
    asset_id = create_resp.json()["id"]

    response = await client.put(
        f"{MACHINE_ASSETS_PREFIX}/{asset_id}",
        headers=crud_auth_headers,
        json={"modello": "HR-300C", "matricola": "SN99999"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["modello"] == "HR-300C"
    assert data["matricola"] == "SN99999"


@pytest.mark.asyncio
async def test_soft_delete_machine_asset(client: AsyncClient, crud_auth_headers, crud_company):
    create_resp = await client.post(
        MACHINE_ASSETS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "company_id": crud_company["id"],
            "marca": "DeWalt",
            "modello": "DW-700",
        },
    )
    assert create_resp.status_code == 201
    asset_id = create_resp.json()["id"]

    response = await client.delete(
        f"{MACHINE_ASSETS_PREFIX}/{asset_id}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 204

    response = await client.get(
        f"{MACHINE_ASSETS_PREFIX}/{asset_id}",
        headers=crud_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_machine_asset_unauthenticated(client: AsyncClient, crud_company):
    response = await client.post(
        MACHINE_ASSETS_PREFIX + "/",
        json={
            "company_id": crud_company["id"],
            "marca": "NoAuth",
            "modello": "NA-001",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_machine_asset_cross_tenant(client: AsyncClient, crud_auth_headers, other_auth_headers, crud_company):
    create_resp = await client.post(
        MACHINE_ASSETS_PREFIX + "/",
        headers=crud_auth_headers,
        json={
            "company_id": crud_company["id"],
            "marca": "CrossTenant",
            "modello": "CT-001",
        },
    )
    assert create_resp.status_code == 201
    asset_id = create_resp.json()["id"]

    response = await client.get(
        f"{MACHINE_ASSETS_PREFIX}/{asset_id}",
        headers=other_auth_headers,
    )
    assert response.status_code == 404
