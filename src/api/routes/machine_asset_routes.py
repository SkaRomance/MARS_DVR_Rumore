"""Machine assets API route."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.machine_asset import (
    MachineAssetCreate,
    MachineAssetResponse,
    MachineAssetUpdate,
)
from src.bootstrap.database import get_db
from src.infrastructure.auth.dependencies import get_current_tenant, get_current_user
from src.infrastructure.database.models.noise_source import MachineAsset
from src.infrastructure.database.models.tenant import Tenant
from src.infrastructure.database.models.user import User
from src.infrastructure.middleware.rate_limiter import default_limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=MachineAssetResponse, status_code=status.HTTP_201_CREATED)
async def create_machine_asset(
    data: MachineAssetCreate,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        asset = MachineAsset(
            company_id=data.company_id,
            unit_site_id=data.unit_site_id,
            source_catalog_id=data.source_catalog_id,
            marca=data.marca,
            modello=data.modello,
            matricola=data.matricola,
            acquisition_date=data.acquisition_date,
            version=1,
            tenant_id=tenant.id,
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        return MachineAssetResponse.model_validate(asset)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create machine asset: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/", response_model=list[MachineAssetResponse])
async def list_machine_assets(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    company_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        query = select(MachineAsset).where(
            MachineAsset._is_deleted == False,  # noqa: E712
            MachineAsset.tenant_id == tenant.id,
        )

        if company_id:
            query = query.where(MachineAsset.company_id == company_id)

        query = query.order_by(MachineAsset.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        assets = result.scalars().all()
        return [MachineAssetResponse.model_validate(a) for a in assets]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list machine assets: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{asset_id}", response_model=MachineAssetResponse)
async def get_machine_asset(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(MachineAsset).where(
                MachineAsset.id == asset_id,
                MachineAsset._is_deleted == False,  # noqa: E712
                MachineAsset.tenant_id == tenant.id,
            )
        )
        asset = result.scalar_one_or_none()
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine asset {asset_id} not found",
            )
        return MachineAssetResponse.model_validate(asset)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get machine asset: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{asset_id}", response_model=MachineAssetResponse)
async def update_machine_asset(
    asset_id: UUID,
    data: MachineAssetUpdate,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(MachineAsset).where(
                MachineAsset.id == asset_id,
                MachineAsset._is_deleted == False,  # noqa: E712
                MachineAsset.tenant_id == tenant.id,
            )
        )
        asset = result.scalar_one_or_none()
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine asset {asset_id} not found",
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(asset, field, value)

        await db.commit()
        await db.refresh(asset)
        return MachineAssetResponse.model_validate(asset)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update machine asset: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine_asset(
    asset_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        result = await db.execute(
            select(MachineAsset).where(
                MachineAsset.id == asset_id,
                MachineAsset._is_deleted == False,  # noqa: E712
                MachineAsset.tenant_id == tenant.id,
            )
        )
        asset = result.scalar_one_or_none()
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine asset {asset_id} not found",
            )
        asset._is_deleted = True
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete machine asset: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
