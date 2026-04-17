"""Health check route."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.assessment import HealthCheckResponse
from src.bootstrap.config import get_settings
from src.bootstrap.database import get_db
from src.infrastructure.middleware.rate_limiter import (
    _redis_available,
    _redis_connection,
)

settings = get_settings()
router = APIRouter()


async def check_db(db: AsyncSession) -> str:
    try:
        await db.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def check_redis() -> str:
    if _redis_available and _redis_connection:
        try:
            await _redis_connection.ping()
            return "ok"
        except Exception:
            return "error"
    return "unavailable"


@router.get("/", response_model=HealthCheckResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint with DB and Redis status."""
    db_status = await check_db(db)
    redis_status = await check_redis()

    if db_status == "error":
        overall_status = "unhealthy"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif redis_status in ("error", "unavailable"):
        overall_status = "degraded"
        http_status = status.HTTP_200_OK
    else:
        overall_status = "healthy"
        http_status = status.HTTP_200_OK

    from starlette.responses import JSONResponse

    return JSONResponse(
        status_code=http_status,
        content=HealthCheckResponse(
            status=overall_status,
            version=settings.app_version,
            timestamp=datetime.now(UTC),
            db_status=db_status,
            redis_status=redis_status,
        ).model_dump(mode="json"),
    )
