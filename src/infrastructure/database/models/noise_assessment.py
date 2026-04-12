"""NoiseAssessment entity model - central assessment record."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.infrastructure.database.base import Base
from src.infrastructure.database.enums import EntityStatus


class NoiseAssessment(Base):
    """Main noise assessment entity (Art. 190 D.Lgs. 81/2008)."""

    __tablename__ = "noise_assessment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    unit_site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[EntityStatus] = mapped_column(
        String(20), default=EntityStatus.active.value
    )

    assessment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    next_review_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Worker exposure tracking
    workers_count_exposed: Mapped[int | None] = mapped_column(Integer, default=0)
    representative_workers: Mapped[list[str] | None] = mapped_column(
        Text, nullable=True
    )

    # Methodology
    measurement_protocol: Mapped[str | None] = mapped_column(String(255), nullable=True)
    instrument_class: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Versioning
    version: Mapped[int] = mapped_column(default=1)
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Soft delete
    _is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return (
            f"<NoiseAssessment(id={self.id}, status='{self.status}', v{self.version})>"
        )


class NoiseAssessmentResult(Base):
    """Assessment results per job role (LEX,8h, peaks, classification)."""

    __tablename__ = "noise_assessment_result"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    job_role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # LEX values (Art. 190 D.Lgs. 81/2008)
    lex_8h: Mapped[float | None] = mapped_column(
        nullable=True, comment="LEX,8h in dB(A)"
    )
    lex_weekly: Mapped[float | None] = mapped_column(
        nullable=True, comment="LEX,weekly in dB(A) - Art. 190 c.2"
    )

    # Peak values
    lcpeak_db_c: Mapped[float | None] = mapped_column(
        nullable=True, comment="C-weighted peak in dB(C)"
    )

    # Classification (Art. 188)
    risk_band: Mapped[str] = mapped_column(String(20), default="negligible")

    # Incertezza (ISO/IEC Guide 98-3)
    uncertainty_db: Mapped[float | None] = mapped_column(
        nullable=True, comment="Incertezza estesa in dB"
    )
    confidence_score: Mapped[float | None] = mapped_column(
        nullable=True, comment="Confidence score 0-1"
    )

    # K corrections
    k_impulse: Mapped[float] = mapped_column(default=0.0)
    k_tone: Mapped[float] = mapped_column(default=0.0)
    k_background: Mapped[float] = mapped_column(default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<NoiseAssessmentResult(lex={self.lex_8h}dB, band='{self.risk_band}')>"
