"""Pydantic schemas for JobRole CRUD operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobRoleCreate(BaseModel):
    company_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    department: str | None = Field(default=None, max_length=100)
    exposure_level: str | None = Field(default=None, max_length=20)
    risk_band: str | None = Field(default=None, max_length=20)


class JobRoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    department: str | None = Field(default=None, max_length=100)
    exposure_level: str | None = Field(default=None, max_length=20)
    risk_band: str | None = Field(default=None, max_length=20)


class JobRoleResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    company_id: UUID
    name: str
    description: str | None = None
    department: str | None = None
    exposure_level: str | None = None
    risk_band: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)
