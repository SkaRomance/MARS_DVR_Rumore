"""Mitigation measures API route."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.mitigation_measure import (
    MitigationMeasureCreate,
    MitigationMeasureResponse,
    MitigationMeasureUpdate,
)
from src.bootstrap.database import get_db
from src.infrastructure.auth.dependencies import get_current_tenant, get_current_user
from src.infrastructure.database.models.mitigation_measure import MitigationMeasure
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User
from src.infrastructure.middleware.rate_limiter import default_limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=MitigationMeasureResponse, status_code=status.HTTP_201_CREATED)
async def create_mitigation(
    data: MitigationMeasureCreate,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        mitigation = MitigationMeasure(
            assessment_id=data.assessment_id,
            type=data.type,
            title=data.title,
            description=data.description,
            priority=data.priority,
            status=data.status,
            implementation_date=data.implementation_date,
            cost_euro=data.cost_euro,
            approved_by=data.approved_by,
            version=1,
            tenant_id=tenant.id,
        )
        db.add(mitigation)
        await db.commit()
        await db.refresh(mitigation)
        return MitigationMeasureResponse.model_validate(mitigation)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create mitigation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/", response_model=list[MitigationMeasureResponse])
async def list_mitigations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    assessment_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        query = select(MitigationMeasure).where(
            MitigationMeasure._is_deleted == False,  # noqa: E712
            MitigationMeasure.tenant_id == tenant.id,
        )

        if assessment_id:
            query = query.where(MitigationMeasure.assessment_id == assessment_id)

        query = query.order_by(MitigationMeasure.priority.asc(), MitigationMeasure.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        mitigations = result.scalars().all()
        return [MitigationMeasureResponse.model_validate(m) for m in mitigations]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list mitigations: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{measure_id}", response_model=MitigationMeasureResponse)
async def get_mitigation(
    measure_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(MitigationMeasure).where(
                MitigationMeasure.id == measure_id,
                MitigationMeasure._is_deleted == False,  # noqa: E712
                MitigationMeasure.tenant_id == tenant.id,
            )
        )
        mitigation = result.scalar_one_or_none()
        if not mitigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mitigation measure {measure_id} not found",
            )
        return MitigationMeasureResponse.model_validate(mitigation)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get mitigation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{measure_id}", response_model=MitigationMeasureResponse)
async def update_mitigation(
    measure_id: UUID,
    data: MitigationMeasureUpdate,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(MitigationMeasure).where(
                MitigationMeasure.id == measure_id,
                MitigationMeasure._is_deleted == False,  # noqa: E712
                MitigationMeasure.tenant_id == tenant.id,
            )
        )
        mitigation = result.scalar_one_or_none()
        if not mitigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mitigation measure {measure_id} not found",
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(mitigation, field, value)

        await db.commit()
        await db.refresh(mitigation)
        return MitigationMeasureResponse.model_validate(mitigation)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update mitigation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{measure_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mitigation(
    measure_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(MitigationMeasure).where(
                MitigationMeasure.id == measure_id,
                MitigationMeasure._is_deleted == False,  # noqa: E712
                MitigationMeasure.tenant_id == tenant.id,
            )
        )
        mitigation = result.scalar_one_or_none()
        if not mitigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mitigation measure {measure_id} not found",
            )
        mitigation._is_deleted = True
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete mitigation: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
