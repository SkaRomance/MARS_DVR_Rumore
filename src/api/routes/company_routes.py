"""Company API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from src.bootstrap.database import get_db
from src.infrastructure.auth.dependencies import get_current_tenant, get_current_user
from src.infrastructure.database.models.company import Company
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User
from src.infrastructure.middleware.rate_limiter import default_limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    data: CompanyCreate,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        company = Company(
            name=data.name,
            ateco_primary_code=data.ateco_primary_code,
            fiscal_code=data.fiscal_code,
            status="active",
            version=1,
            tenant_id=tenant.id,
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)
        return CompanyResponse.model_validate(company)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create company: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/", response_model=list[CompanyResponse])
async def list_companies(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        query = select(Company).where(
            Company._is_deleted == False,  # noqa: E712
            Company.tenant_id == tenant.id,
        )
        query = query.order_by(Company.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        companies = result.scalars().all()
        return [CompanyResponse.model_validate(c) for c in companies]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list companies: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(Company).where(
                Company.id == company_id,
                Company._is_deleted == False,  # noqa: E712
                Company.tenant_id == tenant.id,
            )
        )
        company = result.scalar_one_or_none()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company {company_id} not found",
            )
        return CompanyResponse.model_validate(company)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get company: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: UUID,
    data: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(Company).where(
                Company.id == company_id,
                Company._is_deleted == False,  # noqa: E712
                Company.tenant_id == tenant.id,
            )
        )
        company = result.scalar_one_or_none()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company {company_id} not found",
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)

        await db.commit()
        await db.refresh(company)
        return CompanyResponse.model_validate(company)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update company: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(Company).where(
                Company.id == company_id,
                Company._is_deleted == False,  # noqa: E712
                Company.tenant_id == tenant.id,
            )
        )
        company = result.scalar_one_or_none()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company {company_id} not found",
            )
        company._is_deleted = True
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete company: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
