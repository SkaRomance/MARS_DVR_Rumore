import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, LargeBinary, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base


class Tenant(Base):
    __tablename__ = "tenant"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    keygen_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    keygen_license_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    license_status: Mapped[str] = mapped_column(String(20), default="inactive")
    logo_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    logo_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    max_assessments: Mapped[int] = mapped_column(Integer, default=10)
    license_activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    license_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    machine_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name='{self.name}', slug='{self.slug}')>"