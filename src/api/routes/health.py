"""Health check route."""

from datetime import datetime
from fastapi import APIRouter

from src.api.schemas.assessment import HealthCheckResponse
from src.bootstrap.config import get_settings

settings = get_settings()
router = APIRouter()


@router.get("/", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version, "timestamp": datetime.utcnow()}
