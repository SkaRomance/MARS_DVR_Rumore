"""Pydantic schemas for AI endpoints."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class InteractionType(StrEnum):
    """Types of AI interactions."""

    BOOTSTRAP = "bootstrap"
    REVIEW = "review"
    EXPLAIN = "explain"
    NARRATIVE = "narrative"
    MITIGATION = "mitigation"
    SOURCE_DETECTION = "source_detection"


class SuggestionStatus(StrEnum):
    """Status of AI suggestions."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


# ============================================================================
# Request Schemas
# ============================================================================


class BootstrapRequest(BaseModel):
    """Request for AI bootstrap."""

    ateco_codes: list[str] = Field(
        ...,
        min_length=1,
        description="List of ATECO 2007 codes",
    )
    company_description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Free-text description of the company",
    )
    existing_data: dict[str, Any] | None = Field(
        default=None,
        description="Existing assessment data if any",
    )


class ReviewRequest(BaseModel):
    """Request for AI review."""

    assessment_id: UUID = Field(..., description="Assessment ID to review")
    assessment_data: dict[str, Any] = Field(
        ...,
        description="Complete assessment JSON data to review",
    )
    company_name: str | None = Field(
        default=None,
        description="Name of the company",
    )
    ateco_code: str | None = Field(
        default=None,
        description="Primary ATECO code",
    )
    focus_areas: list[str] | None = Field(
        default=None,
        description="Specific areas to focus on",
    )


class ExplainRequest(BaseModel):
    """Request for AI explanation."""

    subject: str = Field(
        ...,
        description="Subject to explain (lex_calculation, risk_band, threshold, mitigation)",
    )
    target_id: UUID | None = Field(
        default=None,
        description="Specific element ID to explain",
    )
    level: str = Field(
        default="technical",
        description="Explanation level: beginner, technical, expert",
    )
    context_data: dict[str, Any] | None = Field(
        default=None,
        description="Contextual data for the explanation",
    )


class NarrativeRequest(BaseModel):
    """Request for narrative generation."""

    assessment_id: UUID = Field(..., description="Assessment ID")
    company_name: str = Field(..., description="Company name")
    ateco_code: str = Field(..., description="ATECO code")
    assessment_date: str = Field(..., description="Assessment date")
    responsible_name: str = Field(..., description="Responsible person name")
    results: dict[str, Any] = Field(default_factory=dict, description="Calculation results")
    roles: list[dict[str, Any]] = Field(default_factory=list, description="Job roles data")
    noise_sources: list[dict[str, Any]] = Field(default_factory=list, description="Noise sources")
    mitigations: list[str] = Field(default_factory=list, description="Proposed mitigations")
    section: str | None = Field(
        default=None,
        description="Specific section to generate (or all if not specified)",
    )


class MitigationRequest(BaseModel):
    """Request for mitigation suggestions."""

    lex_levels: dict[str, float] = Field(
        default_factory=dict,
        description="Map of role -> LEX,8h level",
    )
    risk_bands: dict[str, str] = Field(
        default_factory=dict,
        description="Map of role -> risk band",
    )
    affected_roles: list[str] | None = Field(
        default=None,
        description="Specific roles to focus on",
    )
    include_ppe: bool = Field(default=True)
    include_engineering: bool = Field(default=True)
    include_administrative: bool = Field(default=True)


class SourceDetectionRequest(BaseModel):
    """Request for noise source detection."""

    description: str = Field(
        ...,
        min_length=5,
        description="Free-text description to match to noise sources",
    )
    category: str | None = Field(
        default=None,
        description="Filter by machine category",
    )


class SuggestionActionRequest(BaseModel):
    """Request to approve/reject a suggestion."""

    status: SuggestionStatus = Field(..., description="New status")
    feedback: str | None = Field(
        default=None,
        description="Optional feedback for approval/rejection",
    )


# ============================================================================
# Response Schemas
# ============================================================================


class ProcessSuggestionResponse(BaseModel):
    """Suggested work process."""

    name: str
    description: str
    typical_noise_sources: list[str]
    confidence: float


class RoleSuggestionResponse(BaseModel):
    """Suggested job role."""

    name: str
    typical_exposure_hours: float
    processes: list[str]
    confidence: float


class NoiseSourceSuggestionResponse(BaseModel):
    """Suggested noise source."""

    type: str
    typical_noise_level: str
    source_confidence: float


class BootstrapResponse(BaseModel):
    """Response from AI bootstrap."""

    processes: list[ProcessSuggestionResponse]
    roles: list[RoleSuggestionResponse]
    noise_sources: list[NoiseSourceSuggestionResponse]
    missing_data: list[str]
    next_actions: list[str]
    confidence_overall: float


class ReviewIssueResponse(BaseModel):
    """Issue found during review."""

    severity: str
    category: str
    description: str
    location: str | None
    suggestion: str | None


class ReviewResponse(BaseModel):
    """Response from AI review."""

    issues: list[ReviewIssueResponse]
    warnings: list[dict[str, str]]
    missing_data: list[str]
    validation_passed: bool
    overall_score: float


class ExplainResponse(BaseModel):
    """Response from AI explanation."""

    explanation: str
    technical_details: dict[str, Any] | None
    related_regulations: list[str]
    confidence: float


class NarrativeResponse(BaseModel):
    """Response from narrative generation."""

    content: str
    section: str
    word_count: int
    confidence: float


class MitigationControlResponse(BaseModel):
    """A mitigation control."""

    type: str
    description: str
    estimated_effectiveness: float | None = None
    estimated_cost: str | None = None
    priority: int


class MitigationResponse(BaseModel):
    """Response from mitigation suggestion."""

    engineer_controls: list[MitigationControlResponse]
    administrative_controls: list[MitigationControlResponse]
    ppe_recommendations: list[dict[str, Any]]
    priority_order: list[str]
    overall_risk_reduction: str | None


class SourceDetectionResponse(BaseModel):
    """Response from noise source detection."""

    matched_sources: list[dict[str, Any]]
    unmatched_description: str | None
    confidence: float


class SuggestionResponse(BaseModel):
    """Response for a single suggestion."""

    id: UUID
    assessment_id: UUID
    suggestion_type: str
    title: str
    content: dict[str, Any]
    confidence_score: float | None
    status: SuggestionStatus
    created_at: datetime
    approved_at: datetime | None


class InteractionResponse(BaseModel):
    """Response for AI interaction log."""

    id: UUID
    assessment_id: UUID | None
    interaction_type: str
    model_name: str | None
    tokens_used: int | None
    confidence_score: float | None
    created_at: datetime


class HealthResponse(BaseModel):
    """AI service health check."""

    available: bool
    provider: str
    model: str
    latency_ms: float | None
