"""Assessments API route."""

import logging
from datetime import datetime
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.schemas.assessment import (
    AssessmentCreate,
    AssessmentResponse,
    AssessmentUpdate,
    CalculationRequest,
    CalculationResponse,
)
from src.bootstrap.database import get_db
from src.domain.services.noise_calculation import (
    calculate_lex_8h,
    PhaseExposure,
    ExposureOrigin,
)
from src.infrastructure.database.models.noise_assessment import NoiseAssessment
from src.infrastructure.database.enums import EntityStatus

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED
)
async def create_assessment(data: AssessmentCreate):
    """Create a new noise assessment."""
    try:
        async with get_db() as session:
            assessment = NoiseAssessment(
                company_id=data.company_id,
                unit_site_id=data.unit_site_id,
                description=data.description,
                status=EntityStatus.active.value,
                version=1,
                assessment_date=datetime.utcnow(),
            )
            session.add(assessment)
            await session.commit()
            await session.refresh(assessment)

            return AssessmentResponse.model_validate(assessment)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create assessment: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/", response_model=list[AssessmentResponse])
async def list_assessments(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: Optional[str] = Query(default=None, alias="status"),
):
    """List all noise assessments with pagination."""
    try:
        async with get_db() as session:
            query = select(NoiseAssessment).where(
                NoiseAssessment._is_deleted == False  # noqa: E712
            )

            if status_filter:
                query = query.where(NoiseAssessment.status == status_filter)

            query = query.order_by(NoiseAssessment.created_at.desc())
            query = query.offset(skip).limit(limit)

            result = await session.execute(query)
            assessments = result.scalars().all()

            return [AssessmentResponse.model_validate(a) for a in assessments]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list assessments: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(assessment_id: UUID):
    """Get an existing noise assessment."""
    try:
        async with get_db() as session:
            result = await session.execute(
                select(NoiseAssessment).where(
                    NoiseAssessment.id == assessment_id,
                    NoiseAssessment._is_deleted == False,  # noqa: E712
                )
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assessment {assessment_id} not found",
                )

            return AssessmentResponse.model_validate(assessment)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get assessment: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put("/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(assessment_id: UUID, data: AssessmentUpdate):
    """Update an existing noise assessment."""
    try:
        async with get_db() as session:
            result = await session.execute(
                select(NoiseAssessment).where(
                    NoiseAssessment.id == assessment_id,
                    NoiseAssessment._is_deleted == False,  # noqa: E712
                )
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assessment {assessment_id} not found",
                )

            update_data = data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(assessment, field, value)

            await session.commit()
            await session.refresh(assessment)

            return AssessmentResponse.model_validate(assessment)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update assessment: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment(assessment_id: UUID):
    """Soft delete a noise assessment."""
    try:
        async with get_db() as session:
            result = await session.execute(
                select(NoiseAssessment).where(
                    NoiseAssessment.id == assessment_id,
                    NoiseAssessment._is_deleted == False,  # noqa: E712
                )
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assessment {assessment_id} not found",
                )

            assessment._is_deleted = True
            await session.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete assessment: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
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
