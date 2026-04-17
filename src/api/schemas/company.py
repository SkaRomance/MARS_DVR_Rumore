"""Pydantic schemas for Company CRUD operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    ateco_primary_code: str | None = Field(default=None, pattern=r"^[0-9]{2}\.[0-9]{2}\.[0-9]{2}$")
    fiscal_code: str | None = Field(default=None, max_length=16)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Acme Corp Srl",
                "ateco_primary_code": "25.11.00",
                "fiscal_code": "12345678901",
            }
        }
    )


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    ateco_primary_code: str | None = Field(default=None, pattern=r"^[0-9]{2}\.[0-9]{2}\.[0-9]{2}$")
    fiscal_code: str | None = Field(default=None, max_length=16)


class CompanyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    ateco_primary_code: str | None = None
    fiscal_code: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int
    status: str

    model_config = ConfigDict(from_attributes=True)
