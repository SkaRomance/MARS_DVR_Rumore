"""AI Interaction model - Log di tutte le interazioni AI."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class AIInteraction(Base):
    """Log of AI interactions for noise assessment.

    Tracks all AI queries and responses for:
    - Audit trail compliance
    - Cost tracking (tokens used)
    - Quality assurance
    - Debugging
    """

    __tablename__ = "ai_interaction"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False, index=True
    )

    # Context references
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Interaction metadata
    interaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type: bootstrap, review, explain, narrative, mitigation, source_detection",
    )

    # Prompt/Response
    prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # AI Model info
    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    model_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Quality metrics
    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="AI confidence in response (0.0-1.0)",
    )
    tokens_used: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<AIInteraction(id={self.id}, type='{self.interaction_type}')>"
