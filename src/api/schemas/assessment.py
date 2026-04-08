"""Pydantic schemas for API request/response models."""

from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional


class AssessmentCreate(BaseModel):
    """Request schema for creating a new noise assessment."""

    company_id: UUID
    ateco_code: str = Field(
        ...,
        pattern=r"^[0-9]{2}\.[0-9]{2}\.[0-9]{2}$",
        description="ATECO 2007 code (e.g., 25.11.00)",
    )
    description: Optional[str] = None
    unit_site_id: Optional[UUID] = None

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
    unit_site_id: Optional[UUID] = None
    description: Optional[str] = None
    status: str
    version: int
    assessment_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PhaseExposureRequest(BaseModel):
    """Request schema for a single exposure phase."""

    laeq_db_a: float = Field(
        ..., ge=0, le=140, description="A-weighted equivalent continuous sound level"
    )
    duration_hours: float = Field(..., gt=0, le=24, description="Exposure duration in hours")
    origin: str = Field(
        default="estimated", description="Data origin: measured, calculated, estimated"
    )
    lcpeak_db_c: Optional[float] = Field(
        default=None, ge=100, le=170, description="C-weighted peak level"
    )
    background_noise_db_a: Optional[float] = Field(
        default=None, ge=0, le=140, description="Background noise level"
    )


class CalculationRequest(BaseModel):
    """Request schema for noise exposure calculation."""

    assessment_id: UUID
    exposures: list[PhaseExposureRequest]
    apply_k_corrections: bool = Field(
        default=False, description="Apply K corrections (impulse, tone, background)"
    )


class CalculationResponse(BaseModel):
    """Response schema for calculation results."""

    lex_8h: float = Field(description="Daily noise exposure level LEX,8h in dB(A)")
    lex_weekly: Optional[float] = Field(
        default=None, description="Weekly noise exposure level in dB(A)"
    )
    lcpeak_aggregated: Optional[float] = Field(
        default=None, description="Aggregated C-weighted peak in dB(C)"
    )
    uncertainty_db: Optional[float] = Field(default=None, description="Combined uncertainty in dB")
    confidence_score: float = Field(description="Confidence score 0-1")
    risk_band: str = Field(description="Risk band: negligible, low, medium, high, critical")
    k_impulse: float = Field(default=0.0)
    k_tone: float = Field(default=0.0)
    k_background: float = Field(default=0.0)


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime
