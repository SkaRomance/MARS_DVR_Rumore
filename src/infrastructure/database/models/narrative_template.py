"""Narrative Template model - Template personalizzabili per il testo DVR."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Integer, Boolean, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class NarrativeTemplateType:
    """Types of narrative templates."""

    SECTION = "section"
    CHAPTER = "chapter"
    APPENDIX = "appendix"
    CUSTOM = "custom"


class NarrativeTemplate(Base):
    """Configurable narrative templates for DVR reports.

    Templates define the structure and content of narrative
    sections in the noise risk assessment document.
    """

    __tablename__ = "narrative_template"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Identification
    template_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique key for template (e.g., 'noise_chapter_intro')",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Template content
    template_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=NarrativeTemplateType.SECTION,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Template content with Jinja2 placeholders",
    )

    # Variables/placeholders (JSONB for flexibility)
    variables: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Defined template variables with types",
    )

    # Language and localization
    language: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="it",
    )

    # Versioning and status
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="If true, this template is used by default",
    )

    # Category
    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Category: intro, methodology, results, mitigation, conclusion",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<NarrativeTemplate(key='{self.template_key}', v{self.version})>"
