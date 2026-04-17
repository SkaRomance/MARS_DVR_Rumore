import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.main import app
from src.infrastructure.auth.dependencies import require_license
from src.infrastructure.auth.jwt_handler import create_access_token
from src.infrastructure.auth.password import get_password_hash
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User

AI_PREFIX = "/api/v1/noise"
ASSESSMENT_ID = str(uuid.uuid4())


@pytest.fixture
async def ai_tenant(db_session: AsyncSession):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="AI Test Tenant",
        slug=f"ai-test-{uuid.uuid4().hex[:8]}",
        plan="free",
        license_status="inactive",
        max_assessments=10,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def ai_user(db_session: AsyncSession, ai_tenant):
    user = User(
        id=uuid.uuid4(),
        tenant_id=ai_tenant.id,
        email="ai_user@test.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="AI Tester",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def ai_auth_headers(ai_user):
    token = create_access_token(
        {
            "sub": str(ai_user.id),
            "tenant_id": str(ai_user.tenant_id),
            "role": ai_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _mock_provider(available=True, side_effect=None):
    p = MagicMock()
    if side_effect:
        p.is_available = AsyncMock(side_effect=side_effect)
    else:
        p.is_available = AsyncMock(return_value=available)
    return p


@pytest.mark.asyncio
async def test_ai_health_available(client: AsyncClient, ai_auth_headers):
    provider = _mock_provider(available=True)
    from src.api.routes.ai_routes import get_llm_provider

    saved = app.dependency_overrides.get(get_llm_provider)
    app.dependency_overrides[get_llm_provider] = lambda: provider
    try:
        response = await client.get(f"{AI_PREFIX}/ai/health", headers=ai_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["latency_ms"] is not None
    finally:
        if saved is None:
            app.dependency_overrides.pop(get_llm_provider, None)
        else:
            app.dependency_overrides[get_llm_provider] = saved


@pytest.mark.asyncio
async def test_ai_health_unavailable(client: AsyncClient, ai_auth_headers):
    provider = _mock_provider(available=False)
    from src.api.routes.ai_routes import get_llm_provider

    saved = app.dependency_overrides.get(get_llm_provider)
    app.dependency_overrides[get_llm_provider] = lambda: provider
    try:
        response = await client.get(f"{AI_PREFIX}/ai/health", headers=ai_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert data["latency_ms"] is None
    finally:
        if saved is None:
            app.dependency_overrides.pop(get_llm_provider, None)
        else:
            app.dependency_overrides[get_llm_provider] = saved


@pytest.mark.asyncio
async def test_ai_health_exception(client: AsyncClient, ai_auth_headers):
    provider = _mock_provider(side_effect=Exception("connection refused"))
    from src.api.routes.ai_routes import get_llm_provider

    saved = app.dependency_overrides.get(get_llm_provider)
    app.dependency_overrides[get_llm_provider] = lambda: provider
    try:
        response = await client.get(f"{AI_PREFIX}/ai/health", headers=ai_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
    finally:
        if saved is None:
            app.dependency_overrides.pop(get_llm_provider, None)
        else:
            app.dependency_overrides[get_llm_provider] = saved


@pytest.mark.asyncio
async def test_ai_bootstrap_requires_auth(client: AsyncClient):
    response = await client.post(
        f"{AI_PREFIX}/assessments/{ASSESSMENT_ID}/ai/bootstrap",
        json={"ateco_codes": ["25.11.00"], "company_description": "Azienda metalli"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ai_bootstrap_requires_license(client: AsyncClient, ai_auth_headers):
    saved = app.dependency_overrides.get(require_license)

    async def _rl_403():
        raise HTTPException(status_code=403, detail="Valid license required")

    app.dependency_overrides[require_license] = _rl_403
    try:
        response = await client.post(
            f"{AI_PREFIX}/assessments/{ASSESSMENT_ID}/ai/bootstrap",
            json={
                "ateco_codes": ["25.11.00"],
                "company_description": "Azienda metalli",
            },
            headers=ai_auth_headers,
        )
        assert response.status_code == 403
    finally:
        if saved is None:
            app.dependency_overrides.pop(require_license, None)
        else:
            app.dependency_overrides[require_license] = saved


@pytest.mark.asyncio
async def test_ai_bootstrap_success(client: AsyncClient, ai_auth_headers):
    from src.domain.services.agents.bootstrap_agent import (
        BootstrapSuggestion,
        NoiseSourceSuggestion,
        ProcessSuggestion,
        RoleSuggestion,
    )

    mock_result = BootstrapSuggestion(
        processes=[ProcessSuggestion("Lavorazione metalli", "desc", ["pressa"], 0.9)],
        roles=[RoleSuggestion("Operatore torno", 8.0, ["Lavorazione metalli"], 0.85)],
        noise_sources=[NoiseSourceSuggestion("pressa", "85-95 dB(A)", 0.88)],
        missing_data=["misure fonometriche"],
        next_actions=["effettuare misurazioni"],
        confidence_overall=0.87,
    )

    with patch(
        "src.domain.services.agents.bootstrap_agent.BootstrapAgent.suggest",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = await client.post(
            f"{AI_PREFIX}/assessments/{ASSESSMENT_ID}/ai/bootstrap",
            json={
                "ateco_codes": ["25.11.00"],
                "company_description": "Azienda metalli",
            },
            headers=ai_auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert "processes" in data
    assert "confidence_overall" in data


@pytest.mark.asyncio
async def test_ai_review_success(client: AsyncClient, ai_auth_headers):
    from src.domain.services.agents.review_agent import (
        ReviewIssue,
        ReviewResult,
        ReviewWarning,
    )

    mock_result = ReviewResult(
        issues=[ReviewIssue("high", "completeness", "Dati mancanti", "sezione 2", "Inserire")],
        warnings=[ReviewWarning("Verifica", "s1", "controllare")],
        missing_data=["foto"],
        validation_passed=False,
        overall_score=0.65,
    )

    with patch(
        "src.domain.services.agents.review_agent.ReviewAgent.review",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = await client.post(
            f"{AI_PREFIX}/assessments/{ASSESSMENT_ID}/ai/review",
            json={"assessment_id": ASSESSMENT_ID, "assessment_data": {"test": True}},
            headers=ai_auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["validation_passed"] is False


@pytest.mark.asyncio
async def test_ai_explain_success(client: AsyncClient, ai_auth_headers):
    from src.domain.services.agents.explain_agent import ExplainResult, TechnicalDetails

    mock_result = ExplainResult(
        explanation="Spiegazione tecnica",
        technical_details=TechnicalDetails(["LEX=..."], ["D.Lgs.81/2008"], {"lex": 85}),
        related_regulations=["D.Lgs.81/2008 Art.189"],
        confidence=0.92,
    )

    with patch(
        "src.domain.services.agents.explain_agent.ExplainAgent.explain",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = await client.post(
            f"{AI_PREFIX}/assessments/{ASSESSMENT_ID}/ai/explain",
            json={"subject": "lex_calculation", "level": "technical"},
            headers=ai_auth_headers,
        )

    assert response.status_code == 200
    assert "explanation" in response.json()


@pytest.mark.asyncio
async def test_ai_narrative_success(client: AsyncClient, ai_auth_headers):
    from src.domain.services.agents.narrative_agent import (
        NarrativeResult,
        NarrativeSection,
    )

    mock_result = NarrativeResult(
        sections=[NarrativeSection("Premessa", "Testo", "input")],
        full_text="Testo narrativo DVR",
        word_count=42,
        confidence=0.88,
    )

    with patch(
        "src.domain.services.agents.narrative_agent.NarrativeAgent.generate",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = await client.post(
            f"{AI_PREFIX}/assessments/{ASSESSMENT_ID}/ai/narrative",
            json={
                "assessment_id": ASSESSMENT_ID,
                "company_name": "Test S.r.l.",
                "ateco_code": "25.11.00",
                "assessment_date": "2024-01-01",
                "responsible_name": "Mario Rossi",
            },
            headers=ai_auth_headers,
        )

    assert response.status_code == 200
    assert response.json()["word_count"] == 42


@pytest.mark.asyncio
async def test_ai_mitigation_success(client: AsyncClient, ai_auth_headers):
    from src.domain.services.agents.mitigation_agent import (
        AdministrativeControl,
        EngineeringControl,
        MitigationResult,
        PPERecommendation,
    )

    mock_result = MitigationResult(
        engineer_controls=[EngineeringControl("enclosure", "Capotta", 0.15, "medio", 1)],
        administrative_controls=[AdministrativeControl("rotation", "Rotazione", 0.05, 2)],
        ppe_recommendations=[PPERecommendation("otoprotettori", 25, "Inserti", ["operaio"], 1)],
        priority_order=["enclosure"],
        overall_risk_reduction="-5 dB",
        confidence=0.85,
    )

    with patch(
        "src.domain.services.agents.mitigation_agent.MitigationAgent.suggest",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = await client.post(
            f"{AI_PREFIX}/assessments/{ASSESSMENT_ID}/ai/suggest-mitigations",
            json={"lex_levels": {"operaio": 85}, "risk_bands": {"operaio": "medium"}},
            headers=ai_auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["engineer_controls"]) == 1


@pytest.mark.asyncio
async def test_ai_detect_sources_success(client: AsyncClient, ai_auth_headers):
    from src.domain.services.agents.source_detection_agent import (
        DetectedSource,
        SourceDetectionResult,
    )

    mock_result = SourceDetectionResult(
        detected_sources=[DetectedSource("pressa", "Pressa meccanica", "85-95 dB(A)", 0.9, "pressa")],
        confidence_overall=0.9,
        processing_notes="2 fonti trovate",
    )

    with patch(
        "src.domain.services.agents.source_detection_agent.SourceDetectionAgent.detect",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = await client.post(
            f"{AI_PREFIX}/assessments/{ASSESSMENT_ID}/ai/detect-sources",
            json={"description": "Reparto lavorazione metalli con presse e torni"},
            headers=ai_auth_headers,
        )

    assert response.status_code == 200
    assert "matched_sources" in response.json()


@pytest.mark.asyncio
async def test_get_suggestions_empty(client: AsyncClient, ai_auth_headers):
    response = await client.get(
        f"{AI_PREFIX}/assessments/{ASSESSMENT_ID}/ai/suggestions",
        headers=ai_auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_suggestion_action_not_found(client: AsyncClient, ai_auth_headers):
    random_id = str(uuid.uuid4())
    response = await client.post(
        f"{AI_PREFIX}/assessments/{ASSESSMENT_ID}/ai/suggestions/{random_id}/action",
        json={"status": "approved"},
        headers=ai_auth_headers,
    )
    assert response.status_code == 404
