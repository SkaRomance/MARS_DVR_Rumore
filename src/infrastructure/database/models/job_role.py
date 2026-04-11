"""JobRole entity model - Job roles/mansioni with exposure data."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, func, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.infrastructure.database.base import Base


class JobRole(Base):
    """Job role entity with exposure tracking."""

    __tablename__ = "job_role"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exposure_level: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    risk_band: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(default=1)
    _is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<JobRole(id={self.id}, name='{self.name}', exposure='{self.exposure_level}')>"
