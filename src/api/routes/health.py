"""Health check routes.

Exposes the standard Kubernetes-style probes:

* ``GET /health/``        — legacy aggregated status (kept for backwards compat).
* ``GET /health/live``    — liveness. Always 200 when the process is running.
* ``GET /health/ready``   — readiness. 200 only when DB is reachable. Redis
                            is treated as best-effort (see rate-limiter fallback
                            pattern); a missing Redis connection yields a
                            ``degraded`` readiness but still 200 so that the
                            app stays in the load-balancer rotation.
* ``GET /health/startup`` — returns 200 once app bootstrap has completed.
                            Flipped by ``mark_startup_complete()`` from the
                            FastAPI lifespan hook.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from src.api.schemas.assessment import HealthCheckResponse
from src.bootstrap.config import get_settings
from src.bootstrap.database import get_db
from src.infrastructure.middleware.rate_limiter import (
    _redis_available,
    _redis_connection,
)

settings = get_settings()
router = APIRouter()

# Startup flag flipped by the lifespan hook once bootstrap is complete.
_startup_complete: bool = False


def mark_startup_complete() -> None:
    """Mark the application as fully bootstrapped.

    Called from the FastAPI lifespan after DB/Redis init succeeds so the
    ``/health/startup`` probe can report readiness.
    """
    global _startup_complete
    _startup_complete = True


def reset_startup_complete() -> None:
    """Reset the startup flag. Intended for tests and shutdown."""
    global _startup_complete
    _startup_complete = False


async def check_db(db: AsyncSession) -> str:
    try:
        await db.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def check_redis() -> str:
    """Redis check that never hard-fails.

    Mirrors the fallback used by :mod:`src.infrastructure.middleware.rate_limiter`:
    a missing Redis connection reports ``unavailable`` instead of raising so
    local dev and unit tests (which run without Redis) don't trip the probe.
    """
    if _redis_available and _redis_connection:
        try:
            await _redis_connection.ping()
            return "ok"
        except Exception:
            return "error"
    return "unavailable"


@router.get("/", response_model=HealthCheckResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Legacy aggregated health endpoint (kept for backwards compatibility)."""
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


@router.get("/live")
async def liveness():
    """Liveness probe — always 200 when the process is running."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "alive",
            "version": settings.app_version,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@router.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Readiness probe — checks DB (hard) and Redis (soft).

    Returns 503 only when the database is unreachable. Redis being
    unavailable produces a ``degraded`` status but keeps a 200 so the
    process stays in the load balancer rotation (Redis is only used for
    rate limiting and already has a permissive fallback).
    """
    db_status = await check_db(db)
    redis_status = await check_redis()

    if db_status != "ok":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "db_status": db_status,
                "redis_status": redis_status,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    overall = "ready" if redis_status == "ok" else "degraded"
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": overall,
            "db_status": db_status,
            "redis_status": redis_status,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@router.get("/startup")
async def startup_probe():
    """Startup probe — 200 once :func:`mark_startup_complete` has been called."""
    if _startup_complete:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "started",
                "version": settings.app_version,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "starting",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
