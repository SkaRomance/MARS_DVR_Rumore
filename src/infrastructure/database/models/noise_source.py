"""Noise source catalog model - machine/emission data."""

import uuid
from datetime import date, datetime
from sqlalchemy import String, Date, DateTime, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base


class NoiseSourceCatalog(Base):
    """Catalog of noise sources with typical emission levels."""

    __tablename__ = "noise_source_catalog"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Identification
    marca: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    modello: Mapped[str] = mapped_column(String(255), nullable=False)
    tipologia: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alimentazione: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Emission data (dichiarati dal costruttore)
    laeq_min_db_a: Mapped[float | None] = mapped_column(
        Numeric(5, 1), nullable=True, comment="Min LAeq typical range"
    )
    laeq_max_db_a: Mapped[float | None] = mapped_column(
        Numeric(5, 1), nullable=True, comment="Max LAeq typical range"
    )
    laeq_typical_db_a: Mapped[float | None] = mapped_column(
        Numeric(5, 1), nullable=True, comment="Typical LAeq value"
    )
    lcpeak_db_c: Mapped[float | None] = mapped_column(
        Numeric(5, 1), nullable=True, comment="C-weighted peak"
    )

    # Source metadata
    fonte: Mapped[str] = mapped_column(
        String(100), nullable=False, default="PAF - Portale Agenti Fisici"
    )
    url_fonte: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data_aggiornamento: Mapped[date] = mapped_column(
        Date, nullable=False, default=date.today
    )

    # Disclaimer (obbligatorio per uso PAF)
    disclaimer: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="Dati per finalità prevenzione sicurezza lavoro - PAF Portale Agenti Fisici",
    )

    # Versioning
    version: Mapped[int] = mapped_column(default=1)
    _is_deleted: Mapped[bool] = mapped_column(default=False)

    def __repr__(self) -> str:
        return f"<NoiseSourceCatalog('{self.marca} {self.modello}', {self.tipologia})>"


class MachineAsset(Base):
    """Specific machine instance in a company/unit site."""

    __tablename__ = "machine_asset"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    unit_site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Reference to catalog
    source_catalog_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Physical details
    marca: Mapped[str] = mapped_column(String(255), nullable=False)
    modello: Mapped[str] = mapped_column(String(255), nullable=False)
    matricola: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Acquisition
    acquisition_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    version: Mapped[int] = mapped_column(default=1)
    _is_deleted: Mapped[bool] = mapped_column(default=False)

    def __repr__(self) -> str:
        return f"<MachineAsset('{self.marca} {self.modello}', sn={self.matricola})>"
