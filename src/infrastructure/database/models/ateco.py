"""ATECO catalog entity model - ISTAT 2007 classification."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base


class AtecoCatalog(Base):
    """ATECO 2007 classification catalog (ISTAT)."""

    __tablename__ = "ateco_catalog"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        unique=True,
        index=True,
        comment="ATECO 2007 code (e.g., 25.11.00)",
    )
    description: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="ATECO description (Italian)"
    )
    category: Mapped[str | None] = mapped_column(
        String(5), nullable=True, comment="Category letter (A, B, C, ...)"
    )
    section: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Section full description"
    )
    division: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="Division code (2 digits)"
    )
    group: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="Group code (4 digits)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AtecoCatalog(code='{self.code}', desc='{self.description[:50]}...')>"
