"""Pydantic schemas for NoiseAssessmentContext endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContextBootstrapRequest(BaseModel):
    """POST /contexts/bootstrap body."""

    mars_dvr_document_id: uuid.UUID = Field(
        ..., description="MARS DVR document UUID (stable across revisions)",
    )
    mars_revision_id: uuid.UUID | None = Field(
        None,
        description="Optional: specific revision. When omitted, the latest "
                    "published revision is used.",
    )
    force_sync: bool = Field(
        False,
        description="Force re-fetch of DVR snapshot even if local cache is fresh.",
    )


class ContextResponse(BaseModel):
    """GET/POST /contexts/* response body."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    mars_dvr_document_id: uuid.UUID
    mars_revision_id: uuid.UUID
    mars_document_version: int
    dvr_schema_version: str | None
    status: str
    notes: str | None
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # Full snapshot is optional — list endpoints omit it to stay small.
    dvr_snapshot: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class ContextListResponse(BaseModel):
    items: list[ContextResponse]
    total: int


class ContextStatusUpdateRequest(BaseModel):
    """PATCH /contexts/{id}/status body."""

    status: str = Field(
        ...,
        description="One of: bootstrapped, in_progress, completed, abandoned",
    )
