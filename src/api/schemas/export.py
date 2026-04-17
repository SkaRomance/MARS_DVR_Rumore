"""Pydantic schemas for export endpoints."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExportFormat(StrEnum):
    """Supported export formats."""

    JSON = "json"
    DVR_FULL = "dvr_full"
    DVR_SUMMARY = "dvr_summary"


class ExportLanguage(StrEnum):
    """Export language."""

    ITALIAN = "it"
    ENGLISH = "en"


class ExportRequest(BaseModel):
    """Request schema for exporting an assessment."""

    format: ExportFormat = Field(
        default=ExportFormat.DVR_FULL,
        description="Export format",
    )
    language: ExportLanguage = Field(
        default=ExportLanguage.ITALIAN,
        description="Document language",
    )
    include_attachments: bool = Field(
        default=False,
        description="Include measurement attachments",
    )
    include_ai_narrative: bool = Field(
        default=True,
        description="Include AI-generated narrative sections",
    )
    template: str | None = Field(
        default=None,
        description="Custom template name for DVR export",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "format": "dvr_full",
                "language": "it",
                "include_attachments": False,
                "include_ai_narrative": True,
            }
        }
    )


class ExportResponse(BaseModel):
    """Response schema for export operations."""

    assessment_id: UUID
    format: ExportFormat
    filename: str
    content_type: str
    generated_at: datetime
    content: dict[str, Any] | None = None
    download_url: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assessment_id": "550e8400-e29b-41d4-a716-446655440000",
                "format": "dvr_full",
                "filename": "DVR_RUMORE_2024_001.json",
                "content_type": "application/json",
                "generated_at": "2024-01-15T10:30:00Z",
                "download_url": None,
            }
        }
    )


class DVRSezioneIdentificazione(BaseModel):
    """Sezione 1: Identificazione azienda e unità produttiva."""

    ragione_sociale: str
    partita_iva: str | None = None
    codice_fiscale: str | None = None
    ateco_code: str
    ateco_descrizione: str | None = None
    unit_site_name: str | None = None
    indirizzo: str | None = None
    datore_di_lavoro: str
    rls_nome: str | None = None
    rspp_nome: str
    medicocompetente: str | None = None
    assunzione_datore: datetime | None = None


class DVRSezioneProcessi(BaseModel):
    """Sezione 2: Descrizione attività e processi."""

    processi: list[dict[str, Any]]
    mansioni: list[dict[str, Any]]
    macchinari: list[dict[str, Any]]
    note_processo: str | None = None


class DVRSezioneValutazioneRischi(BaseModel):
    """Sezione 3: Valutazione dei rischi."""

    data_valutazione: datetime
    protocollo_misura: str | None = None
    classe_strumento: str | None = None
    risultati_mansione: list[dict[str, Any]]
    rischi_individuati: list[dict[str, Any]]
    soglie_superate: dict[str, Any]


class DVRSezioneMisurePrevenzione(BaseModel):
    """Sezione 4: Misure di prevenzione e protezione."""

    misure_tecniche: list[dict[str, Any]]
    misure_amministrative: list[dict[str, Any]]
    dpi_uditivi: list[dict[str, Any]]
    programma_dpi: dict[str, Any] | None = None


class DVRSezioneSorveglianza(BaseModel):
    """Sezione 6: Sorveglianza sanitaria."""

    obbligo_sorveglianza: bool
    periodicita: str | None = None
    medico_competente: str | None = None
    protocollo_sanitario: str | None = None
    lavoratori_sensibili: list[dict[str, Any]] | None = None


class DVRSezioneFormazione(BaseModel):
    """Sezione 7: Formazione e informazione."""

    formazione_effettuata: bool
    data_ultima_formazione: datetime | None = None
    contenuti_formazione: list[str] | None = None
    attestati: list[dict[str, Any]] | None = None


class DVRDocument(BaseModel):
    """Complete DVR document structure."""

    metadata: dict[str, Any]
    sezione_1_identificazione: DVRSezioneIdentificazione
    sezione_2_processi: DVRSezioneProcessi
    sezione_3_valutazione: DVRSezioneValutazioneRischi
    sezione_4_misure_prevenzione: DVRSezioneMisurePrevenzione
    sezione_6_sorveglianza: DVRSezioneSorveglianza
    sezione_7_formazione: DVRSezioneFormazione
    allegati: list[dict[str, Any]] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metadata": {
                    "versione": "1.0",
                    "data_emissione": "2024-01-15",
                    "normativa": "D.Lgs. 81/2008",
                }
            }
        }
    )


class ExportPreviewResponse(BaseModel):
    assessment_id: UUID
    sections_count: int
    estimated_pages: int | None = None
    has_attachments: bool
    has_ai_narrative: bool
    missing_data: list[str] | None = None
    warnings: list[str] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assessment_id": "550e8400-e29b-41d4-a716-446655440000",
                "sections_count": 9,
                "estimated_pages": 15,
                "has_attachments": False,
                "has_ai_narrative": True,
                "missing_data": ["partita_iva", "codice_fiscale"],
                "warnings": ["Alcuni macchinari non hanno livelli sonori associati"],
            }
        }
    )


class SectionUpdateRequest(BaseModel):
    content_html: str


class TemplateUpdateRequest(BaseModel):
    content: str | None = None
    name: str | None = None
    description: str | None = None
    variables: dict | None = None


class PrintSettingsUpdateRequest(BaseModel):
    company_id: UUID
    header_text: str | None = None
    footer_text: str | None = None
    cover_title: str | None = None
    cover_subtitle: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    font_family: str | None = None
    font_size: int | None = None
    paper_size: str | None = None
    margins: dict | None = None
