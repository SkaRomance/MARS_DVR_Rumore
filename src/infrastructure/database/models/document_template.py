"""DocumentTemplate entity model - Template overrides for DOCX."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, func, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base


class DocumentTemplate(Base):
    """Document template entity for DOCX generation."""

    __tablename__ = "document_template"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_key: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    variables: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="it")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(default=1)

    def __repr__(self) -> str:
        return f"<DocumentTemplate(id={self.id}, key='{self.template_key}', type='{self.template_type}')>"
