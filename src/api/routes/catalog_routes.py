"""Noise source catalog browse routes (read-only)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.database import get_db
from src.infrastructure.auth.dependencies import get_current_user
from src.infrastructure.database.models.noise_source import NoiseSourceCatalog
from src.infrastructure.database.models.user import User
from src.infrastructure.middleware.rate_limiter import default_limiter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_catalog(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    tipologia: str | None = None,
    marca: str | None = None,
    min_laeq: float | None = None,
    max_laeq: float | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        query = select(NoiseSourceCatalog).where(NoiseSourceCatalog._is_deleted == False)  # noqa: E712

        if tipologia:
            query = query.where(NoiseSourceCatalog.tipologia == tipologia)
        if marca:
            query = query.where(NoiseSourceCatalog.marca.ilike(f"%{marca}%"))
        if min_laeq is not None:
            query = query.where(NoiseSourceCatalog.laeq_typical_db_a >= min_laeq)
        if max_laeq is not None:
            query = query.where(NoiseSourceCatalog.laeq_typical_db_a <= max_laeq)

        query = query.order_by(NoiseSourceCatalog.tipologia, NoiseSourceCatalog.marca)
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        sources = result.scalars().all()

        return [
            {
                "id": str(s.id),
                "marca": s.marca,
                "modello": s.modello,
                "tipologia": s.tipologia,
                "alimentazione": s.alimentazione,
                "laeq_min_db_a": float(s.laeq_min_db_a) if s.laeq_min_db_a else None,
                "laeq_max_db_a": float(s.laeq_max_db_a) if s.laeq_max_db_a else None,
                "laeq_typical_db_a": float(s.laeq_typical_db_a) if s.laeq_typical_db_a else None,
                "lcpeak_db_c": float(s.lcpeak_db_c) if s.lcpeak_db_c else None,
                "fonte": s.fonte,
                "data_aggiornamento": s.data_aggiornamento.isoformat() if s.data_aggiornamento else None,
            }
            for s in sources
        ]
    except Exception as e:
        logger.error("Failed to list catalog: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list catalog",
        )


@router.get("/stats")
async def catalog_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    try:
        total = await db.execute(
            select(func.count()).select_from(NoiseSourceCatalog).where(NoiseSourceCatalog._is_deleted == False)  # noqa: E712
        )
        by_type = await db.execute(
            select(NoiseSourceCatalog.tipologia, func.count())
            .where(NoiseSourceCatalog._is_deleted == False)  # noqa: E712
            .group_by(NoiseSourceCatalog.tipologia)
            .order_by(func.count().desc())
        )

        return {
            "total_sources": total.scalar() or 0,
            "by_tipologia": {row[0]: row[1] for row in by_type.all()},
        }
    except Exception as e:
        logger.error("Failed to get catalog stats: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get catalog stats",
        )


@router.get("/{source_id}")
async def get_catalog_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(default_limiter),
):
    from uuid import UUID

    try:
        source_uuid = UUID(source_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid source ID format",
        )

    try:
        result = await db.execute(
            select(NoiseSourceCatalog).where(
                NoiseSourceCatalog.id == source_uuid,
                NoiseSourceCatalog._is_deleted == False,  # noqa: E712
            )
        )
        source = result.scalar_one_or_none()
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        return {
            "id": str(source.id),
            "marca": source.marca,
            "modello": source.modello,
            "tipologia": source.tipologia,
            "alimentazione": source.alimentazione,
            "laeq_min_db_a": float(source.laeq_min_db_a) if source.laeq_min_db_a else None,
            "laeq_max_db_a": float(source.laeq_max_db_a) if source.laeq_max_db_a else None,
            "laeq_typical_db_a": float(source.laeq_typical_db_a) if source.laeq_typical_db_a else None,
            "lcpeak_db_c": float(source.lcpeak_db_c) if source.lcpeak_db_c else None,
            "fonte": source.fonte,
            "url_fonte": source.url_fonte,
            "data_aggiornamento": source.data_aggiornamento.isoformat() if source.data_aggiornamento else None,
            "disclaimer": source.disclaimer,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get source %s: %s", source_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get source",
        )
