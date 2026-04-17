import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.infrastructure.auth.jwt_handler import create_access_token
from src.infrastructure.auth.password import get_password_hash
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User

API = "/api/v1/noise"


def _auth_headers(user):
    token = create_access_token({"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


async def _seed_tenant_user(db_session, role="admin"):
    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"IntTenant-{uuid.uuid4().hex[:6]}",
        slug=f"int-{uuid.uuid4().hex[:8]}",
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
        email=f"{uuid.uuid4().hex[:8]}@inttest.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Integration User",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return tenant, user


@pytest.mark.asyncio
async def test_assessment_with_ai_bootstrap_and_review(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    company_resp = await client.post(
        f"{API}/companies/",
        headers=headers,
        json={
            "name": "AI Workflow Srl",
            "ateco_primary_code": "25.11.00",
            "fiscal_code": "98765432101",
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
            "description": "Integration test AI workflow",
        },
    )
    assert assessment_resp.status_code == 201
    assessment_id = assessment_resp.json()["id"]

    ateco_resp = await client.get(
        f"{API}/ateco/code/25.11.00",
        headers=headers,
    )
    assert ateco_resp.status_code == 200
    assert ateco_resp.json()["ateco_code"] == "25.11.00"
    assert ateco_resp.json()["macro_category"] is not None
    assert ateco_resp.json()["macro_category"]["code"] == "C"

    from src.domain.services.agents.bootstrap_agent import (
        BootstrapSuggestion,
        NoiseSourceSuggestion,
        ProcessSuggestion,
        RoleSuggestion,
    )

    mock_bootstrap = BootstrapSuggestion(
        processes=[ProcessSuggestion("Lavorazione metalli", "desc", ["pressa"], 0.9)],
        roles=[RoleSuggestion("Operatore torno", 8.0, ["Lavorazione metalli"], 0.85)],
        noise_sources=[NoiseSourceSuggestion("pressa", "85-95 dB(A)", 0.88)],
        missing_data=["misure fonometriche"],
        next_actions=["effettuare misurazioni"],
        confidence_overall=0.87,
    )

    from src.domain.services.agents.review_agent import (
        ReviewIssue,
        ReviewResult,
        ReviewWarning,
    )

    mock_review = ReviewResult(
        issues=[ReviewIssue("medium", "completeness", "Dati parziali", "s1", "Integrare")],
        warnings=[ReviewWarning("Verifica livelli", "s2", "controllare")],
        missing_data=["misure"],
        validation_passed=True,
        overall_score=0.78,
    )

    with (
        patch(
            "src.domain.services.agents.bootstrap_agent.BootstrapAgent.suggest",
            new_callable=AsyncMock,
            return_value=mock_bootstrap,
        ),
        patch(
            "src.domain.services.agents.review_agent.ReviewAgent.review",
            new_callable=AsyncMock,
            return_value=mock_review,
        ),
    ):
        bootstrap_resp = await client.post(
            f"{API}/assessments/{assessment_id}/ai/bootstrap",
            headers=headers,
            json={
                "ateco_codes": ["25.11.00"],
                "company_description": "Azienda lavorazione metalli",
            },
        )
        assert bootstrap_resp.status_code == 200
        assert "processes" in bootstrap_resp.json()
        assert bootstrap_resp.json()["confidence_overall"] == 0.87

        review_resp = await client.post(
            f"{API}/assessments/{assessment_id}/ai/review",
            headers=headers,
            json={
                "assessment_id": str(assessment_id),
                "assessment_data": {"test": True},
            },
        )
        assert review_resp.status_code == 200
        assert review_resp.json()["validation_passed"] is True

    suggestions_resp = await client.get(
        f"{API}/assessments/{assessment_id}/ai/suggestions",
        headers=headers,
    )
    assert suggestions_resp.status_code == 200
    assert isinstance(suggestions_resp.json(), list)


@pytest.mark.asyncio
async def test_assessment_calculate_and_export_json(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    company_resp = await client.post(
        f"{API}/companies/",
        headers=headers,
        json={"name": "Calc Export Srl", "ateco_primary_code": "25.11.00"},
    )
    assert company_resp.status_code == 201
    company_id = company_resp.json()["id"]

    assessment_resp = await client.post(
        f"{API}/",
        headers=headers,
        json={
            "company_id": company_id,
            "ateco_code": "25.11.00",
            "description": "Calculate and export test",
        },
    )
    assert assessment_resp.status_code == 201
    assessment_id = assessment_resp.json()["id"]

    calc_resp = await client.post(
        f"{API}/calculate",
        headers=headers,
        json={
            "assessment_id": str(assessment_id),
            "exposures": [
                {
                    "laeq_db_a": 85.0,
                    "duration_hours": 8.0,
                    "origin": "measured",
                }
            ],
        },
    )
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()
    assert "lex_8h" in calc_data
    assert "risk_band" in calc_data
    assert calc_data["risk_band"] in ("medium", "high", "low", "negligible", "critical")

    json_export_resp = await client.post(
        f"{API}/export/assessments/{assessment_id}/json",
        headers=headers,
        json={"format": "json", "language": "it"},
    )
    assert json_export_resp.status_code == 200
    export_data = json_export_resp.json()
    assert export_data["assessment_id"] == assessment_id
    assert "content" in export_data


@pytest.mark.asyncio
async def test_ai_cross_tenant_isolation(client: AsyncClient, db_session):
    tenant_a, user_a = await _seed_tenant_user(db_session, role="admin")
    tenant_b, user_b = await _seed_tenant_user(db_session, role="admin")
    headers_a = _auth_headers(user_a)
    headers_b = _auth_headers(user_b)

    comp_a_resp = await client.post(
        f"{API}/companies/",
        headers=headers_a,
        json={"name": "TenantA Co", "ateco_primary_code": "25.11.00"},
    )
    assert comp_a_resp.status_code == 201
    company_a_id = comp_a_resp.json()["id"]

    assessment_a_resp = await client.post(
        f"{API}/",
        headers=headers_a,
        json={
            "company_id": company_a_id,
            "ateco_code": "25.11.00",
            "description": "Tenant A assessment",
        },
    )
    assert assessment_a_resp.status_code == 201
    assessment_a_id = assessment_a_resp.json()["id"]

    comp_b_resp = await client.post(
        f"{API}/companies/",
        headers=headers_b,
        json={"name": "TenantB Co", "ateco_primary_code": "25.11.00"},
    )
    assert comp_b_resp.status_code == 201
    company_b_id = comp_b_resp.json()["id"]

    assessment_b_resp = await client.post(
        f"{API}/",
        headers=headers_b,
        json={
            "company_id": company_b_id,
            "ateco_code": "25.11.00",
            "description": "Tenant B assessment",
        },
    )
    assert assessment_b_resp.status_code == 201
    assessment_b_id = assessment_b_resp.json()["id"]

    get_b_as_a = await client.get(
        f"{API}/{assessment_b_id}",
        headers=headers_a,
    )
    assert get_b_as_a.status_code == 404

    get_a_as_b = await client.get(
        f"{API}/{assessment_a_id}",
        headers=headers_b,
    )
    assert get_a_as_b.status_code == 404

    suggestions_a = await client.get(
        f"{API}/assessments/{assessment_a_id}/ai/suggestions",
        headers=headers_a,
    )
    assert suggestions_a.status_code == 200

    suggestions_b_for_a = await client.get(
        f"{API}/assessments/{assessment_a_id}/ai/suggestions",
        headers=headers_b,
    )
    assert suggestions_b_for_a.status_code == 200
    assert suggestions_b_for_a.json() == []


@pytest.mark.asyncio
async def test_ateco_code_matches_company(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    company_resp = await client.post(
        f"{API}/companies/",
        headers=headers,
        json={
            "name": "MetallCo Srl",
            "ateco_primary_code": "25.11.00",
            "fiscal_code": "11122233304",
        },
    )
    assert company_resp.status_code == 201

    ateco_resp = await client.get(
        f"{API}/ateco/code/25.11.00",
        headers=headers,
    )
    assert ateco_resp.status_code == 200
    ateco_data = ateco_resp.json()
    assert ateco_data["ateco_code"] == "25.11.00"
    assert ateco_data["macro_category"] is not None
    assert ateco_data["macro_category"]["code"] == "C"


@pytest.mark.asyncio
async def test_full_crud_with_soft_delete_company(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    company_resp = await client.post(
        f"{API}/companies/",
        headers=headers,
        json={"name": "SoftDeleteCo Srl", "ateco_primary_code": "25.11.00"},
    )
    assert company_resp.status_code == 201
    company_id = company_resp.json()["id"]

    jr_resp = await client.post(
        f"{API}/job-roles/",
        headers=headers,
        json={
            "company_id": company_id,
            "name": "Operatore Macchina",
            "department": "Produzione",
            "exposure_level": "high",
        },
    )
    assert jr_resp.status_code == 201

    delete_resp = await client.delete(
        f"{API}/companies/{company_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    list_resp = await client.get(f"{API}/companies/", headers=headers)
    assert list_resp.status_code == 200
    company_ids = [c["id"] for c in list_resp.json()]
    assert company_id not in company_ids

    get_resp = await client.get(f"{API}/companies/{company_id}", headers=headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_export_docx_after_ai_narrative(client: AsyncClient, db_session):
    tenant, user = await _seed_tenant_user(db_session)
    headers = _auth_headers(user)

    company_resp = await client.post(
        f"{API}/companies/",
        headers=headers,
        json={"name": "Narrative Export Srl", "ateco_primary_code": "25.11.00"},
    )
    assert company_resp.status_code == 201
    company_id = company_resp.json()["id"]

    assessment_resp = await client.post(
        f"{API}/",
        headers=headers,
        json={
            "company_id": company_id,
            "ateco_code": "25.11.00",
            "description": "Narrative + DOCX export test",
        },
    )
    assert assessment_resp.status_code == 201
    assessment_id = assessment_resp.json()["id"]

    from src.domain.services.agents.narrative_agent import (
        NarrativeResult,
        NarrativeSection,
    )

    mock_narrative = NarrativeResult(
        sections=[NarrativeSection("Premessa", "Testo narrativo DVR", "input")],
        full_text="Testo narrativo completo per il documento DVR.",
        word_count=10,
        confidence=0.91,
    )

    with patch(
        "src.domain.services.agents.narrative_agent.NarrativeAgent.generate",
        new_callable=AsyncMock,
        return_value=mock_narrative,
    ):
        narrative_resp = await client.post(
            f"{API}/assessments/{assessment_id}/ai/narrative",
            headers=headers,
            json={
                "assessment_id": str(assessment_id),
                "company_name": "Narrative Export Srl",
                "ateco_code": "25.11.00",
                "assessment_date": "2024-06-15",
                "responsible_name": "Ing. Bianchi",
            },
        )
        assert narrative_resp.status_code == 200
        assert narrative_resp.json()["word_count"] == 10

    docx_resp = await client.post(
        f"{API}/export/assessments/{assessment_id}/docx",
        headers=headers,
        json={"format": "dvr_full", "language": "it"},
    )
    assert docx_resp.status_code == 200
    assert (
        docx_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(docx_resp.content) > 1000
