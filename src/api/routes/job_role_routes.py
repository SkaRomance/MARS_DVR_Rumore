"""Job roles API route."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.job_role import JobRoleCreate, JobRoleResponse, JobRoleUpdate
from src.bootstrap.database import get_db
from src.infrastructure.auth.dependencies import get_current_tenant, get_current_user
from src.infrastructure.database.models.job_role import JobRole
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User
from src.infrastructure.middleware.rate_limiter import default_limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=JobRoleResponse, status_code=status.HTTP_201_CREATED)
async def create_job_role(
    data: JobRoleCreate,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        job_role = JobRole(
            company_id=data.company_id,
            name=data.name,
            description=data.description,
            department=data.department,
            exposure_level=data.exposure_level,
            risk_band=data.risk_band,
            version=1,
            tenant_id=tenant.id,
        )
        db.add(job_role)
        await db.commit()
        await db.refresh(job_role)
        return JobRoleResponse.model_validate(job_role)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create job role: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/", response_model=list[JobRoleResponse])
async def list_job_roles(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    company_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        query = select(JobRole).where(
            JobRole._is_deleted == False,  # noqa: E712
            JobRole.tenant_id == tenant.id,
        )

        if company_id:
            query = query.where(JobRole.company_id == company_id)

        query = query.order_by(JobRole.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        job_roles = result.scalars().all()
        return [JobRoleResponse.model_validate(jr) for jr in job_roles]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list job roles: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{job_role_id}", response_model=JobRoleResponse)
async def get_job_role(
    job_role_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(JobRole).where(
                JobRole.id == job_role_id,
                JobRole._is_deleted == False,  # noqa: E712
                JobRole.tenant_id == tenant.id,
            )
        )
        job_role = result.scalar_one_or_none()
        if not job_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job role {job_role_id} not found",
            )
        return JobRoleResponse.model_validate(job_role)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get job role: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{job_role_id}", response_model=JobRoleResponse)
async def update_job_role(
    job_role_id: UUID,
    data: JobRoleUpdate,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(JobRole).where(
                JobRole.id == job_role_id,
                JobRole._is_deleted == False,  # noqa: E712
                JobRole.tenant_id == tenant.id,
            )
        )
        job_role = result.scalar_one_or_none()
        if not job_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job role {job_role_id} not found",
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(job_role, field, value)

        await db.commit()
        await db.refresh(job_role)
        return JobRoleResponse.model_validate(job_role)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update job role: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{job_role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_role(
    job_role_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(JobRole).where(
                JobRole.id == job_role_id,
                JobRole._is_deleted == False,  # noqa: E712
                JobRole.tenant_id == tenant.id,
            )
        )
        job_role = result.scalar_one_or_none()
        if not job_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job role {job_role_id} not found",
            )
        job_role._is_deleted = True
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete job role: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
