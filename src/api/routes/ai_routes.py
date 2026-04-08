"""AI routes for noise assessment assistance."""

import time
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from src.api.schemas.ai import (
    BootstrapRequest,
    BootstrapResponse,
    ReviewRequest,
    ReviewResponse,
    ExplainRequest,
    ExplainResponse,
    NarrativeRequest,
    NarrativeResponse,
    MitigationRequest,
    MitigationResponse,
    SourceDetectionRequest,
    SourceDetectionResponse,
    SuggestionActionRequest,
    SuggestionResponse,
    InteractionResponse,
    HealthResponse,
    InteractionType,
    SuggestionStatus,
)
from src.bootstrap.config import get_settings, Settings
from src.infrastructure.llm import OllamaProvider, MockProvider

logger = logging.getLogger(__name__)
router = APIRouter()


def get_llm_provider(settings: Settings = Depends(get_settings)):
    """Get LLM provider based on settings."""
    if settings.ollama_api_key:
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
            model=settings.ollama_model,
        )
    else:
        return MockProvider()


@router.get("/health", response_model=HealthResponse)
async def ai_health_check(provider=Depends(get_llm_provider)):
    """Check AI service health."""
    start = time.time()

    try:
        available = await provider.is_available()
        latency = (time.time() - start) * 1000

        return HealthResponse(
            available=available,
            provider="ollama",
            model=get_settings().ollama_model,
            latency_ms=latency if available else None,
        )
    except Exception as e:
        logger.error("AI health check failed: %s", e)
        return HealthResponse(
            available=False,
            provider="ollama",
            model=get_settings().ollama_model,
            latency_ms=None,
        )


@router.post(
    "/assessments/{assessment_id}/ai/bootstrap", response_model=BootstrapResponse
)
async def ai_bootstrap(
    assessment_id: UUID,
    request: BootstrapRequest,
    settings: Settings = Depends(get_settings),
):
    """AI-guided initial assessment setup.

    Analyzes ATECO codes and company description to suggest:
    - Work processes
    - Job roles
    - Noise sources
    - Missing data
    - Next actions
    """
    from src.domain.services.agents.bootstrap_agent import (
        BootstrapAgent,
        BootstrapInput,
    )
    from src.domain.services.ai_orchestrator import AIOrchestrator
    from src.infrastructure.llm import OllamaProvider

    try:
        provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
            model=settings.ollama_model,
        )
        orchestrator = AIOrchestrator(provider)
        agent = BootstrapAgent(orchestrator)

        input_data = BootstrapInput(
            ateco_codes=request.ateco_codes,
            company_description=request.company_description,
            existing_data=request.existing_data,
        )

        result = await agent.suggest(input_data, assessment_id=assessment_id)

        return BootstrapResponse(
            processes=[p.__dict__ for p in result.processes],
            roles=[r.__dict__ for r in result.roles],
            noise_sources=[n.__dict__ for n in result.noise_sources],
            missing_data=result.missing_data,
            next_actions=result.next_actions,
            confidence_overall=result.confidence_overall,
        )

    except Exception as e:
        logger.error("Bootstrap failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI bootstrap failed: {str(e)}",
        )


@router.post("/assessments/{assessment_id}/ai/review", response_model=ReviewResponse)
async def ai_review(
    assessment_id: UUID,
    request: ReviewRequest,
    settings: Settings = Depends(get_settings),
):
    """Review existing assessment data.

    Validates:
    - Completeness
    - Consistency
    - Correctness
    - Coverage
    """
    from src.domain.services.agents.review_agent import (
        ReviewAgent,
    )
    from src.domain.services.ai_orchestrator import AIOrchestrator
    from src.infrastructure.llm import OllamaProvider

    try:
        provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
            model=settings.ollama_model,
        )
        orchestrator = AIOrchestrator(provider)
        agent = ReviewAgent(orchestrator)

        assessment_data = request.assessment_data
        company_name = request.company_name or "Azienda sconosciuta"
        ateco_code = request.ateco_code or "Sconosciuto"

        result = await agent.review(
            assessment_data=assessment_data,
            company_name=company_name,
            ateco_code=ateco_code,
            assessment_id=assessment_id,
            focus_areas=request.focus_areas,
        )

        return ReviewResponse(
            issues=[i.__dict__ for i in result.issues],
            warnings=[w.__dict__ for w in result.warnings],
            missing_data=result.missing_data,
            validation_passed=result.validation_passed,
            overall_score=result.overall_score,
        )

    except Exception as e:
        logger.error("Review failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI review failed: {str(e)}",
        )


@router.post("/assessments/{assessment_id}/ai/explain", response_model=ExplainResponse)
async def ai_explain(
    assessment_id: UUID,
    request: ExplainRequest,
    settings: Settings = Depends(get_settings),
):
    """Explain calculations, risk decisions, or regulations.

    Provides explanations at three levels:
    - beginner: Simple, non-technical
    - technical: With proper terminology
    - expert: With derivations and references
    """
    from src.domain.services.agents.explain_agent import (
        ExplainAgent,
    )
    from src.domain.services.ai_orchestrator import AIOrchestrator
    from src.infrastructure.llm import OllamaProvider

    try:
        provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
            model=settings.ollama_model,
        )
        orchestrator = AIOrchestrator(provider)
        agent = ExplainAgent(orchestrator)

        result = await agent.explain(
            subject=request.subject,
            level=request.level,
            context_data=request.context_data or {},
            assessment_id=assessment_id,
            target_id=request.target_id,
        )

        return ExplainResponse(
            explanation=result.explanation,
            technical_details=result.technical_details.__dict__
            if result.technical_details
            else None,
            related_regulations=result.related_regulations,
            confidence=result.confidence,
        )

    except Exception as e:
        logger.error("Explain failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI explain failed: {str(e)}",
        )


@router.post(
    "/assessments/{assessment_id}/ai/narrative", response_model=NarrativeResponse
)
async def ai_generate_narrative(
    assessment_id: UUID,
    request: NarrativeRequest,
    settings: Settings = Depends(get_settings),
):
    """Generate DVR narrative text.

    Creates structured narrative sections for the noise
    risk assessment document following Italian DVR format.
    """
    from src.domain.services.agents.narrative_agent import NarrativeAgent
    from src.domain.services.ai_orchestrator import AIOrchestrator
    from src.infrastructure.llm import OllamaProvider

    try:
        provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
            model=settings.ollama_model,
        )
        orchestrator = AIOrchestrator(provider)
        agent = NarrativeAgent(orchestrator)

        result = await agent.generate(
            company_name=request.company_name,
            ateco_code=request.ateco_code,
            assessment_date=request.assessment_date,
            responsible_name=request.responsible_name,
            results=request.results,
            roles=request.roles,
            noise_sources=request.noise_sources,
            mitigations=request.mitigations,
            assessment_id=assessment_id,
            section=request.section,
        )

        return NarrativeResponse(
            content=result.full_text,
            section=request.section or "full",
            word_count=result.word_count,
            confidence=result.confidence,
        )

    except Exception as e:
        logger.error("Narrative generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI narrative generation failed: {str(e)}",
        )


@router.post(
    "/assessments/{assessment_id}/ai/suggest-mitigations",
    response_model=MitigationResponse,
)
async def ai_suggest_mitigations(
    assessment_id: UUID,
    request: MitigationRequest,
    settings: Settings = Depends(get_settings),
):
    """Suggest risk mitigation measures.

    Based on risk bands and affected roles, suggests:
    - Engineering controls
    - Administrative controls
    - PPE recommendations

    Follows Italian D.Lgs. 81/2008 hierarchy.
    """
    from src.domain.services.agents.mitigation_agent import MitigationAgent
    from src.domain.services.ai_orchestrator import AIOrchestrator
    from src.infrastructure.llm import OllamaProvider

    try:
        provider = OllamaProvider(
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key,
            model=settings.ollama_model,
        )
        orchestrator = AIOrchestrator(provider)
        agent = MitigationAgent(orchestrator)

        result = await agent.suggest(
            lex_levels=request.lex_levels,
            risk_bands=request.risk_bands,
            affected_roles=request.affected_roles,
            assessment_id=assessment_id,
            include_ppe=request.include_ppe,
            include_engineering=request.include_engineering,
            include_administrative=request.include_administrative,
        )

        return MitigationResponse(
            engineer_controls=[c.__dict__ for c in result.engineer_controls],
            administrative_controls=[
                c.__dict__ for c in result.administrative_controls
            ],
            ppe_recommendations=[p.__dict__ for p in result.ppe_recommendations],
            priority_order=result.priority_order,
            overall_risk_reduction=result.overall_risk_reduction,
        )

    except Exception as e:
        logger.error("Mitigation suggestion failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI mitigation suggestion failed: {str(e)}",
        )


@router.post(
    "/assessments/{assessment_id}/ai/detect-sources",
    response_model=SourceDetectionResponse,
)
async def ai_detect_sources(
    assessment_id: UUID,
    request: SourceDetectionRequest,
):
    """Detect noise sources from free-text description.

    Matches descriptions to PAF noise source catalog
    and suggests typical noise levels.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Source detection endpoint not yet implemented",
    )


@router.get(
    "/assessments/{assessment_id}/ai/suggestions",
    response_model=list[SuggestionResponse],
)
async def get_suggestions(
    assessment_id: UUID,
    status_filter: SuggestionStatus | None = None,
):
    """Get AI suggestions for an assessment."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Suggestions list endpoint not yet implemented",
    )


@router.post("/assessments/{assessment_id}/ai/suggestions/{suggestion_id}/action")
async def suggestion_action(
    assessment_id: UUID,
    suggestion_id: UUID,
    request: SuggestionActionRequest,
):
    """Approve or reject an AI suggestion."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Suggestion action endpoint not yet implemented",
    )


@router.get(
    "/assessments/{assessment_id}/ai/interactions",
    response_model=list[InteractionResponse],
)
async def get_interactions(
    assessment_id: UUID,
):
    """Get AI interaction history for an assessment."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Interactions list endpoint not yet implemented",
    )
