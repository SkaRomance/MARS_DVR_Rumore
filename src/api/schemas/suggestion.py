"""Pydantic schemas for V2 suggestion endpoints (Wave 27)."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class SuggestionApproveRequest(BaseModel):
    edited_payload: dict[str, Any] | None = Field(
        None, description="If provided, the suggestion is approved with edits."
    )


class SuggestionRejectRequest(BaseModel):
    reason: str | None = Field(
        None, description="Optional human-readable rejection reason."
    )


class SuggestionBulkRequest(BaseModel):
    suggestion_ids: list[uuid.UUID]
    action: Literal["approve", "reject"]
    min_confidence: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="For approve: only process suggestions with confidence ≥ this.",
    )
    reason: str | None = Field(
        None, description="For reject: applied to every rejected suggestion."
    )


class SuggestionBulkResponse(BaseModel):
    processed: int
    total_requested: int
    failed: list[dict[str, Any]]
