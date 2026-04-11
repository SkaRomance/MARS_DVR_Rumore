"""PrintSettings entity model - Company print configuration."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base


class PrintSettings(Base):
    """Print settings entity for company document styling."""

    __tablename__ = "print_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    header_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    footer_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cover_subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(7), default="#1a365d")
    secondary_color: Mapped[str] = mapped_column(String(7), default="#2c5282")
    font_family: Mapped[str] = mapped_column(String(100), default="Times New Roman")
    font_size: Mapped[int] = mapped_column(Integer, default=12)
    paper_size: Mapped[str] = mapped_column(String(10), default="A4")
    margins: Mapped[dict] = mapped_column(
        JSONB(), default={"top": 25, "bottom": 25, "left": 20, "right": 20}
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(default=1)

    def __repr__(self) -> str:
        return f"<PrintSettings(id={self.id}, company_id={self.company_id})>"
