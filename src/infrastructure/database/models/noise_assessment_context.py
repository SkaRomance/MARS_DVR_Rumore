"""NoiseAssessmentContext — binds a Rumore working session to a MARS DVR document.

The frontend (iframe embed) calls POST /contexts/bootstrap with a MARS
dvr_document_id + revision_id. The backend creates (or returns) a
NoiseAssessmentContext, fetches the DVR snapshot from MARS, and
persists it locally for offline AI analysis.

All Rumore-specific data (noise measurements, AI suggestions, audit
entries) references a context_id — the single identifier that links
an assessment session to MARS.

Snapshot caching rationale:
- Rumore's AI autopilot processes the DVR offline (no round-trips to
  MARS per phase). Snapshot freshness is explicitly tracked via
  last_synced_at; callers can force-refresh.
- Stale contexts (>7 days) are re-synced on bootstrap.

Status lifecycle:
  bootstrapped -> in_progress -> completed | abandoned
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class NoiseAssessmentContextStatus(str, enum.Enum):
    """Lifecycle states for a Rumore assessment session."""

    bootstrapped = "bootstrapped"
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


class NoiseAssessmentContext(Base):
    """One row per Rumore working session tied to a MARS DVR document."""

    __tablename__ = "noise_assessment_context"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "mars_dvr_document_id", "mars_revision_id",
            name="uq_noise_assessment_context_tenant_doc_rev",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
        comment="MARS user id of the consultant who opened the context",
    )

    mars_dvr_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
        comment="MARS DVR document UUID — stable across revisions",
    )
    mars_revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
        comment="MARS DVR revision UUID — one revision per snapshot",
    )
    mars_document_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Revision version number as reported by MARS",
    )

    dvr_snapshot: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Full DVR snapshot from MARS (schema v1.0 or v1.1). "
                "Includes work_phases, phase_equipments, company_data, etc.",
    )
    dvr_schema_version: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="Schema version of the cached snapshot (1.0.0 / 1.1.0)",
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        default=NoiseAssessmentContextStatus.bootstrapped.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When dvr_snapshot was last fetched from MARS",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<NoiseAssessmentContext(id={self.id}, "
            f"doc={self.mars_dvr_document_id}, "
            f"rev={self.mars_revision_id}, "
            f"status={self.status})>"
        )
