"""Pydantic schemas for API request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssessmentCreate(BaseModel):
    """Request schema for creating a new noise assessment."""

    company_id: UUID
    ateco_code: str = Field(
        ...,
        pattern=r"^[0-9]{2}\.[0-9]{2}\.[0-9]{2}$",
        description="ATECO 2007 code (e.g., 25.11.00)",
    )
    description: str | None = None
    unit_site_id: UUID | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company_id": "550e8400-e29b-41d4-a716-446655440000",
                "ateco_code": "25.11.00",
                "description": "Valutazione rischio rumore reparto produzione",
            }
        }
    )


class AssessmentResponse(BaseModel):
    """Response schema for assessment operations."""

    id: UUID
    company_id: UUID
    unit_site_id: UUID | None = None
    description: str | None = None
    status: str
    version: int
    assessment_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PhaseExposureRequest(BaseModel):
    """Request schema for a single exposure phase."""

    laeq_db_a: float = Field(..., ge=0, le=140, description="A-weighted equivalent continuous sound level")
    duration_hours: float = Field(..., gt=0, le=24, description="Exposure duration in hours")
    origin: str = Field(default="estimated", description="Data origin: measured, calculated, estimated")
    lcpeak_db_c: float | None = Field(default=None, ge=100, le=170, description="C-weighted peak level")
    background_noise_db_a: float | None = Field(default=None, ge=0, le=140, description="Background noise level")


class CalculationRequest(BaseModel):
    """Request schema for noise exposure calculation."""

    assessment_id: UUID
    exposures: list[PhaseExposureRequest]
    apply_k_corrections: bool = Field(default=False, description="Apply K corrections (impulse, tone, background)")


class CalculationResponse(BaseModel):
    """Response schema for calculation results."""

    lex_8h: float = Field(description="Daily noise exposure level LEX,8h in dB(A)")
    lex_weekly: float | None = Field(default=None, description="Weekly noise exposure level in dB(A)")
    lcpeak_aggregated: float | None = Field(default=None, description="Aggregated C-weighted peak in dB(C)")
    uncertainty_db: float | None = Field(default=None, description="Combined uncertainty in dB")
    confidence_score: float = Field(description="Confidence score 0-1")
    risk_band: str = Field(description="Risk band: negligible, low, medium, high, critical")
    k_impulse: float = Field(default=0.0)
    k_tone: float = Field(default=0.0)
    k_background: float = Field(default=0.0)


class AssessmentUpdate(BaseModel):
    """Request schema for partially updating a noise assessment."""

    description: str | None = None
    status: str | None = None
    version: int | None = None
    unit_site_id: UUID | None = None


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime
    db_status: str = "unknown"
    redis_status: str = "unknown"
