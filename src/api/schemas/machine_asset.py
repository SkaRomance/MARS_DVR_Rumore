"""Pydantic schemas for MachineAsset CRUD operations."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MachineAssetCreate(BaseModel):
    company_id: UUID
    source_catalog_id: UUID | None = None
    unit_site_id: UUID | None = None
    marca: str = Field(..., min_length=1, max_length=255)
    modello: str = Field(..., min_length=1, max_length=255)
    matricola: str | None = Field(default=None, max_length=100)
    acquisition_date: date | None = None


class MachineAssetUpdate(BaseModel):
    source_catalog_id: UUID | None = None
    unit_site_id: UUID | None = None
    marca: str | None = Field(default=None, min_length=1, max_length=255)
    modello: str | None = Field(default=None, min_length=1, max_length=255)
    matricola: str | None = Field(default=None, max_length=100)
    acquisition_date: date | None = None


class MachineAssetResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    company_id: UUID
    source_catalog_id: UUID | None = None
    unit_site_id: UUID | None = None
    marca: str
    modello: str
    matricola: str | None = None
    acquisition_date: date | None = None
    created_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)
