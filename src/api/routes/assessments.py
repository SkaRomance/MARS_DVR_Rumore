"""Assessments API route."""

from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, status

from src.api.schemas.assessment import (
    AssessmentCreate,
    AssessmentResponse,
    CalculationRequest,
    CalculationResponse,
)
from src.domain.services.noise_calculation import (
    calculate_lex_8h,
    PhaseExposure,
    ExposureOrigin,
)

router = APIRouter()


@router.post(
    "/", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED
)
async def create_assessment(data: AssessmentCreate):
    """Create a new noise assessment."""
    return AssessmentResponse(
        id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        company_id=data.company_id,
        unit_site_id=data.unit_site_id,
        description=data.description,
        status="draft",
        version=1,
        assessment_date=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(assessment_id: UUID):
    """Get an existing noise assessment."""
    return AssessmentResponse(
        id=assessment_id,
        company_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        description="Valutazione rischio rumore",
        status="draft",
        version=1,
        assessment_date=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@router.post("/calculate", response_model=CalculationResponse)
async def calculate_exposure(request: CalculationRequest):
    """Calculate noise exposure for an assessment."""
    exposures = [
        PhaseExposure(
            laeq_db_a=exp.laeq_db_a,
            duration_hours=exp.duration_hours,
            origin=ExposureOrigin(exp.origin),
            lcpeak_db_c=exp.lcpeak_db_c,
            background_noise_db_a=exp.background_noise_db_a,
        )
        for exp in request.exposures
    ]

    result = calculate_lex_8h(exposures)

    return CalculationResponse(
        lex_8h=result.lex_8h,
        lex_weekly=result.lex_weekly,
        lcpeak_aggregated=result.lcpeak_aggregated,
        uncertainty_db=result.uncertainty_db,
        confidence_score=result.confidence_score,
        risk_band=result.risk_band,
        k_impulse=result.k_impulse,
        k_tone=result.k_tone,
        k_background=result.k_background,
    )
