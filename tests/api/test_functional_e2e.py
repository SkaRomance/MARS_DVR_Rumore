import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from src.infrastructure.auth.jwt_handler import create_access_token
from src.infrastructure.auth.password import get_password_hash
from src.infrastructure.database.enums import EntityStatus
from src.infrastructure.database.models.company import Company
from src.infrastructure.database.models.noise_assessment import NoiseAssessment
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User

API = "/api/v1/noise"


def _auth_headers(user):
    token = create_access_token({"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


async def _seed_tenant_user(db_session, role="consultant"):
    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"Tenant-{uuid.uuid4().hex[:6]}",
        slug=f"t-{uuid.uuid4().hex[:8]}",
        plan="free",
        license_status="inactive",
        max_assessments=10,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return tenant, user


@pytest.mark.asyncio
async def test_full_workflow_create_company_assessment_export(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    company_resp = await client.post(
        f"{API}/companies/",
        headers=headers,
        json={
            "name": "Workflow Test Srl",
            "ateco_primary_code": "25.11.00",
            "fiscal_code": "12345678901",
        },
    )
    assert company_resp.status_code == 201
    company_id = company_resp.json()["id"]

    assessment_resp = await client.post(
        f"{API}/",
        headers=headers,
        json={
            "company_id": company_id,
            "ateco_code": "25.11.00",
            "description": "Full workflow test",
        },
    )
    assert assessment_resp.status_code == 201
    assessment_id = assessment_resp.json()["id"]

    json_export_resp = await client.post(
        f"{API}/export/assessments/{assessment_id}/json",
        headers=headers,
        json={"format": "json", "language": "it"},
    )
    assert json_export_resp.status_code == 200
    json_data = json_export_resp.json()
    assert json_data["assessment_id"] == assessment_id
    assert json_data["content"]["status"] == EntityStatus.active.value

    docx_export_resp = await client.post(
        f"{API}/export/assessments/{assessment_id}/docx",
        headers=headers,
        json={"format": "dvr_full", "language": "it"},
    )
    assert docx_export_resp.status_code == 200
    assert (
        docx_export_resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(docx_export_resp.content) > 1000

    doc_resp = await client.get(
        f"{API}/export/assessments/{assessment_id}/document",
        headers=headers,
    )
    assert doc_resp.status_code == 200
    assert doc_resp.json()["metadata"]["assessment_id"] == assessment_id


@pytest.mark.asyncio
async def test_crud_company_full_lifecycle(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    create_resp = await client.post(f"{API}/companies/", headers=headers, json={"name": "ACME Srl"})
    assert create_resp.status_code == 201
    company_id = create_resp.json()["id"]
    assert create_resp.json()["name"] == "ACME Srl"

    list_resp = await client.get(f"{API}/companies/", headers=headers)
    assert list_resp.status_code == 200
    assert any(c["id"] == company_id for c in list_resp.json())

    get_resp = await client.get(f"{API}/companies/{company_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "ACME Srl"

    update_resp = await client.put(
        f"{API}/companies/{company_id}",
        headers=headers,
        json={"name": "ACME Srl Updated", "ateco_primary_code": "25.11.00"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "ACME Srl Updated"

    delete_resp = await client.delete(f"{API}/companies/{company_id}", headers=headers)
    assert delete_resp.status_code == 204

    get_deleted = await client.get(f"{API}/companies/{company_id}", headers=headers)
    assert get_deleted.status_code == 404


@pytest.mark.asyncio
async def test_crud_job_role_with_company(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    company = Company(id=uuid.uuid4(), tenant_id=tenant.id, name="JR Test Co")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    create_resp = await client.post(
        f"{API}/job-roles/",
        headers=headers,
        json={
            "company_id": str(company.id),
            "name": "Operatore Cnc",
            "department": "Produzione",
            "exposure_level": "high",
        },
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["name"] == "Operatore Cnc"
    assert create_resp.json()["exposure_level"] == "high"

    list_resp = await client.get(f"{API}/job-roles/", headers=headers)
    assert list_resp.status_code == 200

    filter_resp = await client.get(
        f"{API}/job-roles/?company_id={company.id}",
        headers=headers,
    )
    assert filter_resp.status_code == 200
    assert len(filter_resp.json()) >= 1


@pytest.mark.asyncio
async def test_crud_machine_asset_with_company(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    company = Company(id=uuid.uuid4(), tenant_id=tenant.id, name="MA Test Co")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    create_resp = await client.post(
        f"{API}/machine-assets/",
        headers=headers,
        json={
            "company_id": str(company.id),
            "marca": "Festool",
            "modello": "CS 70",
            "matricola": "SN12345",
        },
    )
    assert create_resp.status_code == 201
    asset_id = create_resp.json()["id"]
    assert create_resp.json()["marca"] == "Festool"

    get_resp = await client.get(f"{API}/machine-assets/{asset_id}", headers=headers)
    assert get_resp.status_code == 200

    update_resp = await client.put(
        f"{API}/machine-assets/{asset_id}",
        headers=headers,
        json={"matricola": "SN99999"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["matricola"] == "SN99999"


@pytest.mark.asyncio
async def test_crud_mitigation_with_assessment(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    company = Company(id=uuid.uuid4(), tenant_id=tenant.id, name="Mit Test Co")
    db_session.add(company)
    await db_session.commit()

    assessment = NoiseAssessment(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        company_id=company.id,
        description="Test assessment",
        status=EntityStatus.active.value,
        assessment_date=datetime.now(UTC),
        version=1,
    )
    db_session.add(assessment)
    await db_session.commit()
    await db_session.refresh(assessment)

    create_resp = await client.post(
        f"{API}/mitigations/",
        headers=headers,
        json={
            "assessment_id": str(assessment.id),
            "type": "engineering",
            "title": "Silenziatore macchina",
            "priority": 1,
        },
    )
    assert create_resp.status_code == 201
    measure_id = create_resp.json()["id"]
    assert create_resp.json()["type"] == "engineering"

    filter_resp = await client.get(
        f"{API}/mitigations/?assessment_id={assessment.id}",
        headers=headers,
    )
    assert filter_resp.status_code == 200
    assert len(filter_resp.json()) >= 1

    update_resp = await client.put(
        f"{API}/mitigations/{measure_id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "completed"

    delete_resp = await client.delete(f"{API}/mitigations/{measure_id}", headers=headers)
    assert delete_resp.status_code == 204

    get_deleted = await client.get(f"{API}/mitigations/{measure_id}", headers=headers)
    assert get_deleted.status_code == 404


@pytest.mark.asyncio
async def test_print_settings_with_company(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    company = Company(id=uuid.uuid4(), tenant_id=tenant.id, name="PS Test Co")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    save_resp = await client.put(
        f"{API}/export/print-settings",
        headers=headers,
        json={
            "company_id": str(company.id),
            "primary_color": "#FF0000",
            "font_size": 14,
            "header_text": "Custom Header",
        },
    )
    assert save_resp.status_code == 200

    get_resp = await client.get(
        f"{API}/export/print-settings?company_id={company.id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["primary_color"] == "#FF0000"
    assert data["font_size"] == 14


@pytest.mark.asyncio
async def test_cross_tenant_isolation_all_crud(client: AsyncClient, db_session):
    tenant_a, user_a = await _seed_tenant_user(db_session, role="consultant")
    tenant_b, user_b = await _seed_tenant_user(db_session, role="consultant")
    headers_a = _auth_headers(user_a)
    headers_b = _auth_headers(user_b)

    company_a_resp = await client.post(f"{API}/companies/", headers=headers_a, json={"name": "Company A"})
    assert company_a_resp.status_code == 201
    company_a_id = company_a_resp.json()["id"]

    get_a_as_b = await client.get(f"{API}/companies/{company_a_id}", headers=headers_b)
    assert get_a_as_b.status_code == 404

    update_a_as_b = await client.put(f"{API}/companies/{company_a_id}", headers=headers_b, json={"name": "Hacked"})
    assert update_a_as_b.status_code == 404

    delete_a_as_b = await client.delete(f"{API}/companies/{company_a_id}", headers=headers_b)
    assert delete_a_as_b.status_code == 404

    jr_resp = await client.post(
        f"{API}/job-roles/",
        headers=headers_a,
        json={"company_id": company_a_id, "name": "Worker A"},
    )
    assert jr_resp.status_code == 201
    jr_id = jr_resp.json()["id"]
    get_jr_as_b = await client.get(f"{API}/job-roles/{jr_id}", headers=headers_b)
    assert get_jr_as_b.status_code == 404

    asset_resp = await client.post(
        f"{API}/machine-assets/",
        headers=headers_a,
        json={"company_id": company_a_id, "marca": "Brand A", "modello": "Model A"},
    )
    assert asset_resp.status_code == 201
    asset_id = asset_resp.json()["id"]
    get_asset_as_b = await client.get(f"{API}/machine-assets/{asset_id}", headers=headers_b)
    assert get_asset_as_b.status_code == 404


@pytest.mark.asyncio
async def test_auth_required_on_all_crud(client: AsyncClient, db_session):
    endpoints = [
        ("POST", f"{API}/companies/", {"name": "Unauthorized"}),
        ("GET", f"{API}/companies/", None),
        ("GET", f"{API}/job-roles/", None),
        ("GET", f"{API}/machine-assets/", None),
        ("GET", f"{API}/mitigations/", None),
        ("GET", f"{API}/catalog/", None),
    ]
    for method, url, body in endpoints:
        if method == "POST":
            resp = await client.post(url, json=body)
        else:
            resp = await client.get(url)
        assert resp.status_code == 401, f"{method} {url} should return 401, got {resp.status_code}"


@pytest.mark.asyncio
async def test_catalog_read_only(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    list_resp = await client.get(f"{API}/catalog/", headers=headers)
    assert list_resp.status_code == 200
    assert isinstance(list_resp.json(), list)

    stats_resp = await client.get(f"{API}/catalog/stats", headers=headers)
    assert stats_resp.status_code == 200
    assert "total_sources" in stats_resp.json()

    random_uuid = str(uuid.uuid4())
    get_resp = await client.get(f"{API}/catalog/{random_uuid}", headers=headers)
    assert get_resp.status_code == 404
