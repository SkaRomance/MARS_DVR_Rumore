import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from src.infrastructure.auth.jwt_handler import create_access_token
from src.infrastructure.auth.password import get_password_hash
from src.infrastructure.database.enums import EntityStatus
from src.infrastructure.database.models.company import Company
from src.infrastructure.database.models.noise_assessment import (
    NoiseAssessment,
    NoiseAssessmentResult,
)
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User

EXPORT_PREFIX = "/api/v1/noise/export"


@pytest.fixture
async def seeded_tenant(db_session):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Export Test Tenant",
        slug=f"export-test-{uuid.uuid4().hex[:8]}",
        plan="free",
        license_status="inactive",
        max_assessments=10,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def seeded_user(db_session, seeded_tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=seeded_tenant.id,
        email="exporter@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Export Tester",
        role="consultant",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def seeded_auth_headers(seeded_user):
    token = create_access_token(
        {
            "sub": str(seeded_user.id),
            "tenant_id": str(seeded_user.tenant_id),
            "role": seeded_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded_company(db_session, seeded_tenant):
    company = Company(
        id=uuid.uuid4(),
        tenant_id=seeded_tenant.id,
        name="Acme Corp Srl",
        ateco_primary_code="25.11.00",
        fiscal_code="12345678901",
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company


@pytest.fixture
async def seeded_assessment(db_session, seeded_tenant, seeded_company):
    assessment = NoiseAssessment(
        id=uuid.uuid4(),
        tenant_id=seeded_tenant.id,
        company_id=seeded_company.id,
        description="Test noise assessment",
        status=EntityStatus.active.value,
        assessment_date=datetime.now(UTC),
        measurement_protocol="ISO 9612:2009",
        instrument_class="1",
        workers_count_exposed=5,
        version=1,
    )
    db_session.add(assessment)
    await db_session.commit()
    await db_session.refresh(assessment)
    return assessment


@pytest.fixture
async def seeded_result(db_session, seeded_tenant, seeded_assessment):
    result = NoiseAssessmentResult(
        id=uuid.uuid4(),
        tenant_id=seeded_tenant.id,
        assessment_id=seeded_assessment.id,
        lex_8h=82.5,
        lex_weekly=80.1,
        lcpeak_db_c=135.0,
        risk_band="medium",
        k_impulse=0.0,
        k_tone=0.0,
        k_background=0.0,
    )
    db_session.add(result)
    await db_session.commit()
    await db_session.refresh(result)
    return result


@pytest.mark.asyncio
async def test_export_json_authenticated(client: AsyncClient, seeded_auth_headers, seeded_assessment, seeded_result):
    response = await client.post(
        f"{EXPORT_PREFIX}/assessments/{seeded_assessment.id}/json",
        headers=seeded_auth_headers,
        json={"format": "json", "language": "it"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["assessment_id"] == str(seeded_assessment.id)
    assert data["format"] == "json"
    assert data["filename"].endswith(".json")
    assert data["content_type"] == "application/json"
    assert data["content"] is not None
    assert data["content"]["status"] == EntityStatus.active.value
    assert len(data["content"]["results"]) == 1
    assert data["content"]["results"][0]["lex_8h"] == 82.5
    assert data["content"]["results"][0]["risk_band"] == "medium"


@pytest.mark.asyncio
async def test_export_json_not_found(client: AsyncClient, seeded_auth_headers):
    random_uuid = str(uuid.uuid4())
    response = await client.post(
        f"{EXPORT_PREFIX}/assessments/{random_uuid}/json",
        headers=seeded_auth_headers,
        json={"format": "json", "language": "it"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_docx_authenticated(client: AsyncClient, seeded_auth_headers, seeded_assessment, seeded_result):
    response = await client.post(
        f"{EXPORT_PREFIX}/assessments/{seeded_assessment.id}/docx",
        headers=seeded_auth_headers,
        json={"format": "dvr_full", "language": "it"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "DVR_RUMORE" in response.headers.get("content-disposition", "")
    assert len(response.content) > 1000


@pytest.mark.asyncio
async def test_export_docx_not_found(client: AsyncClient, seeded_auth_headers):
    random_uuid = str(uuid.uuid4())
    response = await client.post(
        f"{EXPORT_PREFIX}/assessments/{random_uuid}/docx",
        headers=seeded_auth_headers,
        json={"format": "dvr_full", "language": "it"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_preview_authenticated(client: AsyncClient, seeded_auth_headers, seeded_assessment, seeded_result):
    response = await client.get(
        f"{EXPORT_PREFIX}/assessments/{seeded_assessment.id}/preview",
        headers=seeded_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["assessment_id"] == str(seeded_assessment.id)
    assert data["sections_count"] == 6
    assert data["missing_data"] is None or isinstance(data["missing_data"], list)
    assert data["warnings"] is None or isinstance(data["warnings"], list)


@pytest.mark.asyncio
async def test_export_preview_not_found(client: AsyncClient, seeded_auth_headers):
    random_uuid = str(uuid.uuid4())
    response = await client.get(
        f"{EXPORT_PREFIX}/assessments/{random_uuid}/preview",
        headers=seeded_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_dvr_document_authenticated(
    client: AsyncClient, seeded_auth_headers, seeded_assessment, seeded_result
):
    response = await client.get(
        f"{EXPORT_PREFIX}/assessments/{seeded_assessment.id}/document",
        headers=seeded_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert data["metadata"]["assessment_id"] == str(seeded_assessment.id)
    assert "sezione_1_identificazione" in data
    assert "sezione_3_valutazione" in data
    assert data["sezione_1_identificazione"]["ragione_sociale"] == "Acme Corp Srl"
    assert data["sezione_3_valutazione"]["risultati_mansione"][0]["lex_8h"] == 82.5


@pytest.mark.asyncio
async def test_list_document_sections_authenticated(client: AsyncClient, seeded_auth_headers, seeded_assessment):
    response = await client.get(
        f"{EXPORT_PREFIX}/assessments/{seeded_assessment.id}/document/sections",
        headers=seeded_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6
    section_ids = [s["id"] for s in data]
    assert "identificazione" in section_ids
    assert "processi" in section_ids
    assert "valutazione" in section_ids


@pytest.mark.asyncio
async def test_get_single_section_authenticated(client: AsyncClient, seeded_auth_headers, seeded_assessment):
    response = await client.get(
        f"{EXPORT_PREFIX}/assessments/{seeded_assessment.id}/document/sections/identificazione",
        headers=seeded_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "identificazione"
    assert data["title"] == "Identificazione Azienda"
    assert "content_html" in data


@pytest.mark.asyncio
async def test_get_single_section_not_found(client: AsyncClient, seeded_auth_headers, seeded_assessment):
    response = await client.get(
        f"{EXPORT_PREFIX}/assessments/{seeded_assessment.id}/document/sections/nonexistent",
        headers=seeded_auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_document_section_authenticated(client: AsyncClient, seeded_auth_headers, seeded_assessment):
    response = await client.put(
        f"{EXPORT_PREFIX}/assessments/{seeded_assessment.id}/document/sections/valutazione",
        headers=seeded_auth_headers,
        json={"content_html": "<p>Test updated content</p>"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "valutazione"
    assert data["is_modified"] is True
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_list_templates_authenticated(client: AsyncClient, seeded_auth_headers):
    response = await client.get(
        f"{EXPORT_PREFIX}/templates",
        headers=seeded_auth_headers,
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_print_settings_authenticated(client: AsyncClient, seeded_auth_headers):
    response = await client.get(
        f"{EXPORT_PREFIX}/print-settings",
        headers=seeded_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["primary_color"] == "#1a365d"
    assert data["font_family"] == "Times New Roman"
    assert data["paper_size"] == "A4"


@pytest.mark.asyncio
async def test_save_print_settings_authenticated(client: AsyncClient, seeded_auth_headers, seeded_company):
    response = await client.put(
        f"{EXPORT_PREFIX}/print-settings",
        headers=seeded_auth_headers,
        json={
            "company_id": str(seeded_company.id),
            "header_text": "Custom Header",
            "font_size": 14,
            "primary_color": "#FF0000",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_export_json_with_en_language(client: AsyncClient, seeded_auth_headers, seeded_assessment, seeded_result):
    response = await client.post(
        f"{EXPORT_PREFIX}/assessments/{seeded_assessment.id}/json",
        headers=seeded_auth_headers,
        json={"format": "json", "language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "json"


@pytest.mark.asyncio
async def test_cross_tenant_assessment_access(client: AsyncClient, db_session):
    tenant_a = Tenant(
        id=uuid.uuid4(),
        name="Tenant A",
        slug=f"tenant-a-{uuid.uuid4().hex[:8]}",
        plan="free",
        license_status="inactive",
        max_assessments=10,
    )
    tenant_b = Tenant(
        id=uuid.uuid4(),
        name="Tenant B",
        slug=f"tenant-b-{uuid.uuid4().hex[:8]}",
        plan="free",
        license_status="inactive",
        max_assessments=10,
    )
    db_session.add_all([tenant_a, tenant_b])
    await db_session.commit()

    user_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="user-a@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="User A",
        role="consultant",
        is_active=True,
    )
    db_session.add(user_a)
    await db_session.commit()

    company_b = Company(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        name="Tenant B Corp",
    )
    db_session.add(company_b)
    await db_session.commit()

    assessment_b = NoiseAssessment(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        company_id=company_b.id,
        description="Tenant B assessment",
        status=EntityStatus.active.value,
        assessment_date=datetime.now(UTC),
        version=1,
    )
    db_session.add(assessment_b)
    await db_session.commit()

    token_a = create_access_token(
        {
            "sub": str(user_a.id),
            "tenant_id": str(tenant_a.id),
            "role": user_a.role,
        }
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    response = await client.post(
        f"{EXPORT_PREFIX}/assessments/{assessment_b.id}/json",
        headers=headers_a,
        json={"format": "json", "language": "it"},
    )
    assert response.status_code == 404
