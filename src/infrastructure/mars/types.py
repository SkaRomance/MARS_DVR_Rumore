"""Typed Pydantic models for MARS API responses.

Field aliases map camelCase upstream fields (NestJS/Prisma) to snake_case
Python identifiers. `populate_by_name=True` allows constructing the
models from either style (useful in tests).

`extra="allow"` on DVR snapshot types ensures MARS can add fields
without breaking our parsing — we only extract what we need.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MarsMeTenant(BaseModel):
    id: uuid.UUID
    name: str
    role: str


class MarsMeResponse(BaseModel):
    """GET /me response — identifies the acting user + their tenant + modules."""

    user_id: uuid.UUID = Field(alias="userId")
    email: str
    full_name: str | None = Field(default=None, alias="fullName")
    tenant_id: uuid.UUID | None = Field(default=None, alias="tenantId")
    tenants: list[MarsMeTenant] = Field(default_factory=list)
    enabled_modules: list[str] = Field(default_factory=list, alias="enabledModules")
    roles_by_company: dict[str, list[str]] = Field(default_factory=dict, alias="rolesByCompany")

    model_config = ConfigDict(populate_by_name=True)


class MarsModuleVerifyResponse(BaseModel):
    """POST /modules/verify — tenant entitlement check for a module key."""

    enabled: bool
    module_key: str = Field(alias="moduleKey")
    reason: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class MarsDvrCompanyData(BaseModel):
    vat_number: str | None = Field(default=None, alias="vatNumber")
    legal_name: str | None = Field(default=None, alias="legalName")
    ateco_code: str | None = Field(default=None, alias="atecoCode")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MarsDvrWorkPhase(BaseModel):
    id: str
    name: str
    description: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MarsDvrPhaseEquipment(BaseModel):
    id: str
    phase_id: str = Field(alias="phaseId")
    brand: str | None = None
    model: str | None = None
    tipology: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MarsDvrSnapshot(BaseModel):
    """Full DVR document snapshot (schema v1.0 or v1.1 with module_extensions)."""

    schema_version: Literal["1.0.0", "1.1.0"] = Field(alias="schemaVersion")
    company_data: MarsDvrCompanyData = Field(default_factory=MarsDvrCompanyData, alias="companyData")
    work_phases: list[MarsDvrWorkPhase] = Field(default_factory=list, alias="workPhases")
    phase_equipments: list[MarsDvrPhaseEquipment] = Field(default_factory=list, alias="phaseEquipments")
    risks: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    trainings: list[dict[str, Any]] = Field(default_factory=list)
    module_extensions: dict[str, dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MarsDvrRevisionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID = Field(alias="documentId")
    tenant_id: uuid.UUID = Field(alias="tenantId")
    version: int
    status: str  # draft | published | archived
    snapshot: MarsDvrSnapshot
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class MarsModuleSessionResponse(BaseModel):
    """Response to POST /modules/sessions/register."""

    session_id: str = Field(alias="sessionId")
    module_key: str = Field(alias="moduleKey")
    revision_version: int = Field(alias="revisionVersion")
    started_at: datetime = Field(alias="startedAt")

    model_config = ConfigDict(populate_by_name=True)


class MarsContext(BaseModel):
    """Decoded + resolved MARS context for a request.

    Built by the `require_mars_context` FastAPI dependency from the JWT
    claims + cached tenant lookup. Route handlers receive this.
    """

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str | None = None
    enabled_modules: list[str] = Field(default_factory=list)
    access_token: str  # raw bearer for downstream MARS calls
    token_expires_at: datetime | None = None
