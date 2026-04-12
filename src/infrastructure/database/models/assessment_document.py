"""AssessmentDocument entity model - Versioned exported documents."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, func, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base


class AssessmentDocument(Base):
    """Assessment document entity for versioned DOCX exports."""

    __tablename__ = "assessment_document"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str] = mapped_column(String(5), default="it")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    generated_by: Mapped[str] = mapped_column(String(50), default="system")
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    _is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<AssessmentDocument(id={self.id}, assessment_id={self.assessment_id}, v{self.version}, status='{self.status}')>"
