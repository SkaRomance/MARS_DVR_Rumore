"""Pydantic schemas for MitigationMeasure CRUD operations."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MitigationMeasureCreate(BaseModel):
    assessment_id: UUID
    type: str = Field(..., max_length=50, description="engineering, administrative, or ppe")
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    priority: int = Field(default=3, ge=1, le=5)
    status: str = Field(default="pending", max_length=20)
    implementation_date: date | None = None
    cost_euro: Decimal | None = Field(default=None, ge=0)
    approved_by: str | None = Field(default=None, max_length=255)


class MitigationMeasureUpdate(BaseModel):
    type: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    status: str | None = Field(default=None, max_length=20)
    implementation_date: date | None = None
    cost_euro: Decimal | None = Field(default=None, ge=0)
    approved_by: str | None = Field(default=None, max_length=255)


class MitigationMeasureResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    assessment_id: UUID
    type: str
    title: str
    description: str | None = None
    priority: int
    status: str
    implementation_date: date | None = None
    cost_euro: Decimal | None = None
    approved_by: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)
