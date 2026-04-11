"""Export API routes for DVR document generation."""

import logging
from datetime import datetime
from uuid import UUID
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from src.api.schemas.export import (
    ExportRequest,
    ExportResponse,
    ExportPreviewResponse,
    ExportFormat,
    DVRDocument,
)
from src.bootstrap.database import get_db
from src.domain.services.docx_generator import DOCXGenerator
from src.domain.services.template_service import get_template_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Export"])


@router.post(
    "/assessments/{assessment_id}/export/json",
    response_model=ExportResponse,
)
async def export_assessment_json(
    assessment_id: UUID,
    request: ExportRequest,
):
    """Export assessment as JSON document."""
    from sqlalchemy import select
    from src.infrastructure.database.models.noise_assessment import NoiseAssessment
    from src.infrastructure.database.models.noise_assessment import (
        NoiseAssessmentResult,
    )

    try:
        async with get_db() as session:
            result = await session.execute(
                select(NoiseAssessment).where(NoiseAssessment.id == assessment_id)
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assessment {assessment_id} not found",
                )

            results_result = await session.execute(
                select(NoiseAssessmentResult).where(
                    NoiseAssessmentResult.assessment_id == assessment_id
                )
            )
            results = results_result.scalars().all()

            content = {
                "assessment_id": str(assessment_id),
                "assessment_date": assessment.assessment_date.isoformat()
                if assessment.assessment_date
                else None,
                "status": assessment.status,
                "version": assessment.version,
                "measurement_protocol": assessment.measurement_protocol,
                "instrument_class": assessment.instrument_class,
                "workers_count_exposed": assessment.workers_count_exposed,
                "results": [
                    {
                        "lex_8h": r.lex_8h,
                        "lex_weekly": r.lex_weekly,
                        "lcpeak_db_c": r.lcpeak_db_c,
                        "risk_band": r.risk_band,
                        "k_impulse": r.k_impulse,
                        "k_tone": r.k_tone,
                        "k_background": r.k_background,
                    }
                    for r in results
                ],
            }

            filename = f"DVR_RUMORE_{assessment_id}.json"

            return ExportResponse(
                assessment_id=assessment_id,
                format=ExportFormat.JSON,
                filename=filename,
                content_type="application/json",
                generated_at=datetime.utcnow(),
                content=content,
                download_url=None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("JSON export failed for assessment %s: %s", assessment_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"JSON export failed: {str(e)}",
        )


@router.post(
    "/assessments/{assessment_id}/export/docx",
    response_model=ExportResponse,
)
async def export_assessment_docx(
    assessment_id: UUID,
    request: ExportRequest,
):
    """Export assessment as DOCX document."""
    from sqlalchemy import select
    from src.infrastructure.database.models.noise_assessment import NoiseAssessment
    from src.infrastructure.database.models.noise_assessment import (
        NoiseAssessmentResult,
    )
    from src.infrastructure.database.models.assessment_document import (
        AssessmentDocument,
    )
    from src.infrastructure.database.models.company import Company
    from src.infrastructure.database.models.print_settings import PrintSettings

    try:
        async with get_db() as session:
            result = await session.execute(
                select(NoiseAssessment).where(NoiseAssessment.id == assessment_id)
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assessment {assessment_id} not found",
                )

            company_result = await session.execute(
                select(Company).where(Company.id == assessment.company_id)
            )
            company = company_result.scalar_one_or_none()

            print_settings_result = await session.execute(
                select(PrintSettings).where(
                    PrintSettings.company_id == assessment.company_id
                )
            )
            print_settings_record = print_settings_result.scalar_one_or_none()

            results_result = await session.execute(
                select(NoiseAssessmentResult).where(
                    NoiseAssessmentResult.assessment_id == assessment_id
                )
            )
            results = results_result.scalars().all()

            docx_generator = DOCXGenerator()
            template_service = get_template_service()

            sections_content = {}
            section_keys = [
                "identificazione",
                "processi",
                "valutazione",
                "misure_prevenzione",
                "sorveglianza",
                "formazione",
            ]
            for key in section_keys:
                template = await template_service.get_template(f"section_{key}")
                if template:
                    sections_content[key] = template.get(
                        "content", f"<p>Sezione {key}</p>"
                    )
                else:
                    sections_content[key] = (
                        f"<p>Contenuto sezione {key} - Da compilare</p>"
                    )

            if company:
                sections_content["identificazione"] = (
                    f"<h1>Identificazione Azienda</h1>"
                    f"<p><strong>Ragione Sociale:</strong> {company.name}</p>"
                    f"<p><strong>Codice ATECO:</strong> {company.ateco_primary_code or 'N/A'}</p>"
                )

            if results:
                valutazione_html = "<h1>Risultati Valutazione</h1>"
                for r in results:
                    valutazione_html += (
                        f"<p><strong>LEX,8h:</strong> {r.lex_8h} dB(A) - "
                    )
                    valutazione_html += (
                        f"<strong>Classe rischio:</strong> {r.risk_band}</p>"
                    )
                sections_content["valutazione"] = valutazione_html

            print_settings_dict = None
            if print_settings_record:
                print_settings_dict = {
                    "header_text": print_settings_record.header_text,
                    "footer_text": print_settings_record.footer_text,
                    "primary_color": print_settings_record.primary_color,
                    "font_family": print_settings_record.font_family,
                    "margins": print_settings_record.margins,
                }

            docx_bytes = await docx_generator.generate_dvr(
                assessment_id=assessment_id,
                sections_content=sections_content,
                print_settings=print_settings_dict,
                language=request.language.value,
            )

            latest_doc_result = await session.execute(
                select(AssessmentDocument)
                .where(AssessmentDocument.assessment_id == assessment_id)
                .order_by(AssessmentDocument.version.desc())
                .limit(1)
            )
            latest_doc = latest_doc_result.scalar_one_or_none()
            new_version = (latest_doc.version + 1) if latest_doc else 1

            new_document = AssessmentDocument(
                assessment_id=assessment_id,
                version=new_version,
                format="docx",
                language=request.language.value,
                file_path=None,
                content_json=sections_content,
                generated_by="system",
                status="generated",
            )
            session.add(new_document)
            await session.commit()

            filename = f"DVR_RUMORE_{assessment_id}_v{new_version}.docx"

            return ExportResponse(
                assessment_id=assessment_id,
                format=ExportFormat.DVR_FULL,
                filename=filename,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                generated_at=datetime.utcnow(),
                content=None,
                download_url=None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("DOCX export failed for assessment %s: %s", assessment_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DOCX export failed: {str(e)}",
        )


@router.get(
    "/assessments/{assessment_id}/export/preview",
    response_model=ExportPreviewResponse,
)
async def get_export_preview(
    assessment_id: UUID,
):
    """Get export preview without generating full document."""
    from sqlalchemy import select
    from src.infrastructure.database.models.noise_assessment import NoiseAssessment
    from src.infrastructure.database.models.noise_assessment import (
        NoiseAssessmentResult,
    )
    from src.infrastructure.database.models.assessment_document import (
        AssessmentDocument,
    )

    try:
        async with get_db() as session:
            result = await session.execute(
                select(NoiseAssessment).where(NoiseAssessment.id == assessment_id)
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assessment {assessment_id} not found",
                )

            results_result = await session.execute(
                select(NoiseAssessmentResult).where(
                    NoiseAssessmentResult.assessment_id == assessment_id
                )
            )
            results = results_result.scalars().all()

            doc_result = await session.execute(
                select(AssessmentDocument)
                .where(AssessmentDocument.assessment_id == assessment_id)
                .order_by(AssessmentDocument.version.desc())
                .limit(1)
            )
            latest_doc = doc_result.scalar_one_or_none()

            missing_data = []
            warnings = []

            if not assessment.measurement_protocol:
                missing_data.append("measurement_protocol")
            if not assessment.instrument_class:
                missing_data.append("instrument_class")
            if not assessment.workers_count_exposed:
                missing_data.append("workers_count_exposed")

            if not results:
                warnings.append("Nessun risultato di valutazione presente")
                warnings.append(
                    "Il documento DVR non potrà contenere i dati di esposizione"
                )

            sections_count = 6
            estimated_pages = 10 + len(results) if results else 10

            has_attachments = False
            has_ai_narrative = (
                latest_doc is not None and latest_doc.content_json is not None
            )

            return ExportPreviewResponse(
                assessment_id=assessment_id,
                sections_count=sections_count,
                estimated_pages=estimated_pages,
                has_attachments=has_attachments,
                has_ai_narrative=has_ai_narrative,
                missing_data=missing_data if missing_data else None,
                warnings=warnings if warnings else None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Preview generation failed for assessment %s: %s", assessment_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preview generation failed: {str(e)}",
        )


@router.get(
    "/assessments/{assessment_id}/document",
    response_model=DVRDocument,
)
async def get_dvr_document(
    assessment_id: UUID,
):
    """Get full DVR document content."""
    from sqlalchemy import select
    from src.infrastructure.database.models.noise_assessment import NoiseAssessment
    from src.infrastructure.database.models.noise_assessment import (
        NoiseAssessmentResult,
    )
    from src.infrastructure.database.models.assessment_document import (
        AssessmentDocument,
    )
    from src.infrastructure.database.models.company import Company

    try:
        async with get_db() as session:
            result = await session.execute(
                select(NoiseAssessment).where(NoiseAssessment.id == assessment_id)
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assessment {assessment_id} not found",
                )

            doc_result = await session.execute(
                select(AssessmentDocument)
                .where(AssessmentDocument.assessment_id == assessment_id)
                .order_by(AssessmentDocument.version.desc())
                .limit(1)
            )
            latest_doc = doc_result.scalar_one_or_none()

            company_result = await session.execute(
                select(Company).where(Company.id == assessment.company_id)
            )
            company = company_result.scalar_one_or_none()

            results_result = await session.execute(
                select(NoiseAssessmentResult).where(
                    NoiseAssessmentResult.assessment_id == assessment_id
                )
            )
            results = results_result.scalars().all()

            metadata = {
                "assessment_id": str(assessment_id),
                "version": latest_doc.version if latest_doc else 1,
                "generated_at": latest_doc.created_at.isoformat()
                if latest_doc
                else None,
                "status": assessment.status,
            }

            sezione_1 = {
                "ragione_sociale": company.name if company else "N/A",
                "partita_iva": None,
                "codice_fiscale": company.fiscal_code if company else None,
                "ateco_code": company.ateco_primary_code if company else "N/A",
                "ateco_descrizione": None,
                "unit_site_name": None,
                "indirizzo": None,
                "datore_di_lavoro": "Da compilare",
                "rls_nome": None,
                "rspp_nome": "Da compilare",
                "medicocompetente": None,
                "assunzione_datore": None,
            }

            sezione_2 = {
                "processi": [],
                "mansioni": [],
                "macchinari": [],
                "note_processo": None,
            }

            sezione_3 = {
                "data_valutazione": assessment.assessment_date.isoformat()
                if assessment.assessment_date
                else None,
                "protocollo_misura": assessment.measurement_protocol,
                "classe_strumento": assessment.instrument_class,
                "risultati_mansione": [
                    {
                        "lex_8h": r.lex_8h,
                        "lex_weekly": r.lex_weekly,
                        "lcpeak_db_c": r.lcpeak_db_c,
                        "risk_band": r.risk_band,
                    }
                    for r in results
                ],
                "rischi_individuati": [],
                "soglie_superate": {},
            }

            sezione_4 = {
                "misure_tecniche": [],
                "misure_amministrative": [],
                "dpi_uditivi": [],
                "programma_dpi": None,
            }

            sezione_6 = {
                "obbligo_sorveglianza": False,
                "periodicita": None,
                "medico_competente": None,
                "protocollo_sanitario": None,
                "lavoratori_sensibili": None,
            }

            sezione_7 = {
                "formazione_effettuata": False,
                "data_ultima_formazione": None,
                "contenuti_formazione": None,
                "attestati": None,
            }

            return DVRDocument(
                metadata=metadata,
                sezione_1_identificazione=sezione_1,
                sezione_2_processi=sezione_2,
                sezione_3_valutazione=sezione_3,
                sezione_4_misure_prevenzione=sezione_4,
                sezione_6_sorveglianza=sezione_6,
                sezione_7_formazione=sezione_7,
                allegati=None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get DVR document for assessment %s: %s", assessment_id, e
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get DVR document: {str(e)}",
        )


@router.get(
    "/assessments/{assessment_id}/document/sections",
)
async def list_document_sections(
    assessment_id: UUID,
):
    """List all sections with their current content."""
    from sqlalchemy import select
    from src.infrastructure.database.models.noise_assessment import NoiseAssessment
    from src.infrastructure.database.models.assessment_document import (
        AssessmentDocument,
    )

    try:
        async with get_db() as session:
            result = await session.execute(
                select(NoiseAssessment).where(NoiseAssessment.id == assessment_id)
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assessment {assessment_id} not found",
                )

            doc_result = await session.execute(
                select(AssessmentDocument)
                .where(AssessmentDocument.assessment_id == assessment_id)
                .order_by(AssessmentDocument.version.desc())
                .limit(1)
            )
            latest_doc = doc_result.scalar_one_or_none()

            section_definitions = [
                {"id": "identificazione", "title": "Identificazione Azienda"},
                {"id": "processi", "title": "Attività e Processi"},
                {"id": "valutazione", "title": "Valutazione dei Rischi"},
                {"id": "misure_prevenzione", "title": "Misure di Prevenzione"},
                {"id": "sorveglianza", "title": "Sorveglianza Sanitaria"},
                {"id": "formazione", "title": "Formazione e Informazione"},
            ]

            sections = []
            for sec in section_definitions:
                section_content = (
                    f"<p>Sezione {sec['title']} - Contenuto da compilare</p>"
                )
                is_modified = False

                if latest_doc and latest_doc.content_json:
                    section_content = latest_doc.content_json.get(
                        sec["id"], section_content
                    )
                    is_modified = True

                sections.append(
                    {
                        "id": sec["id"],
                        "title": sec["title"],
                        "content_html": section_content,
                        "is_modified": is_modified,
                    }
                )

            return sections

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list sections for assessment %s: %s", assessment_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sections: {str(e)}",
        )


@router.get(
    "/assessments/{assessment_id}/document/sections/{section_id}",
)
async def get_document_section(
    assessment_id: UUID,
    section_id: str,
):
    """Get single section content."""
    from sqlalchemy import select
    from src.infrastructure.database.models.noise_assessment import NoiseAssessment
    from src.infrastructure.database.models.assessment_document import (
        AssessmentDocument,
    )

    try:
        async with get_db() as session:
            result = await session.execute(
                select(NoiseAssessment).where(NoiseAssessment.id == assessment_id)
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assessment {assessment_id} not found",
                )

            doc_result = await session.execute(
                select(AssessmentDocument)
                .where(AssessmentDocument.assessment_id == assessment_id)
                .order_by(AssessmentDocument.version.desc())
                .limit(1)
            )
            latest_doc = doc_result.scalar_one_or_none()

            section_definitions = {
                "identificazione": "Identificazione Azienda",
                "processi": "Attività e Processi",
                "valutazione": "Valutazione dei Rischi",
                "misure_prevenzione": "Misure di Prevenzione",
                "sorveglianza": "Sorveglianza Sanitaria",
                "formazione": "Formazione e Informazione",
            }

            if section_id not in section_definitions:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Section {section_id} not found",
                )

            section_content = f"<p>Sezione {section_definitions[section_id]} - Contenuto da compilare</p>"
            is_modified = False

            if latest_doc and latest_doc.content_json:
                db_content = latest_doc.content_json.get(section_id)
                if db_content:
                    section_content = db_content
                    is_modified = True

            return {
                "id": section_id,
                "title": section_definitions[section_id],
                "content_html": section_content,
                "is_modified": is_modified,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get section %s for assessment %s: %s",
            section_id,
            assessment_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get section: {str(e)}",
        )


@router.put(
    "/assessments/{assessment_id}/document/sections/{section_id}",
)
async def update_document_section(
    assessment_id: UUID,
    section_id: str,
    content: dict,
):
    """Update section content from WYSIWYG editor."""
    from sqlalchemy import select
    from src.infrastructure.database.models.noise_assessment import NoiseAssessment
    from src.infrastructure.database.models.assessment_document import (
        AssessmentDocument,
    )

    try:
        async with get_db() as session:
            result = await session.execute(
                select(NoiseAssessment).where(NoiseAssessment.id == assessment_id)
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Assessment {assessment_id} not found",
                )

            section_definitions = {
                "identificazione": "Identificazione Azienda",
                "processi": "Attività e Processi",
                "valutazione": "Valutazione dei Rischi",
                "misure_prevenzione": "Misure di Prevenzione",
                "sorveglianza": "Sorveglianza Sanitaria",
                "formazione": "Formazione e Informazione",
            }

            if section_id not in section_definitions:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Section {section_id} not found",
                )

            doc_result = await session.execute(
                select(AssessmentDocument)
                .where(AssessmentDocument.assessment_id == assessment_id)
                .order_by(AssessmentDocument.version.desc())
                .limit(1)
            )
            latest_doc = doc_result.scalar_one_or_none()

            new_version = (latest_doc.version + 1) if latest_doc else 1
            content_json = (
                latest_doc.content_json.copy()
                if latest_doc and latest_doc.content_json
                else {}
            )

            new_content = content.get(
                "content_html", f"<p>Sezione {section_definitions[section_id]}</p>"
            )
            content_json[section_id] = new_content

            new_document = AssessmentDocument(
                assessment_id=assessment_id,
                version=new_version,
                format="draft",
                language="it",
                file_path=None,
                content_json=content_json,
                generated_by="user",
                status="draft",
            )
            session.add(new_document)
            await session.commit()

            return {
                "id": section_id,
                "title": section_definitions[section_id],
                "content_html": new_content,
                "is_modified": True,
                "version": new_version,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update section %s for assessment %s: %s",
            section_id,
            assessment_id,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update section: {str(e)}",
        )


@router.get("/templates")
async def list_templates():
    """List all document templates."""
    from sqlalchemy import select
    from src.infrastructure.database.models.document_template import DocumentTemplate

    try:
        async with get_db() as session:
            result = await session.execute(
                select(DocumentTemplate).where(DocumentTemplate.is_active == True)
            )
            templates = result.scalars().all()

            return [
                {
                    "id": str(t.id),
                    "template_key": t.template_key,
                    "name": t.name,
                    "description": t.description,
                    "template_type": t.template_type,
                    "language": t.language,
                    "is_default": t.is_default,
                    "category": t.category,
                }
                for t in templates
            ]

    except Exception as e:
        logger.error("Failed to list templates: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list templates: {str(e)}",
        )


@router.get("/templates/{template_id}")
async def get_template(
    template_id: UUID,
):
    """Get single template detail."""
    from sqlalchemy import select
    from src.infrastructure.database.models.document_template import DocumentTemplate

    try:
        async with get_db() as session:
            result = await session.execute(
                select(DocumentTemplate).where(DocumentTemplate.id == template_id)
            )
            template = result.scalar_one_or_none()

            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Template {template_id} not found",
                )

            return {
                "id": str(template.id),
                "template_key": template.template_key,
                "name": template.name,
                "description": template.description,
                "template_type": template.template_type,
                "content": template.content,
                "variables": template.variables,
                "language": template.language,
                "is_default": template.is_default,
                "category": template.category,
                "created_at": template.created_at.isoformat()
                if template.created_at
                else None,
                "updated_at": template.updated_at.isoformat()
                if template.updated_at
                else None,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get template %s: %s", template_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template: {str(e)}",
        )


@router.put("/templates/{template_id}")
async def update_template(
    template_id: UUID,
    template_data: dict,
):
    """Override template content from DB."""
    from sqlalchemy import select, update
    from src.infrastructure.database.models.document_template import DocumentTemplate

    try:
        async with get_db() as session:
            result = await session.execute(
                select(DocumentTemplate).where(DocumentTemplate.id == template_id)
            )
            template = result.scalar_one_or_none()

            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Template {template_id} not found",
                )

            if "content" in template_data:
                template.content = template_data["content"]
            if "name" in template_data:
                template.name = template_data["name"]
            if "description" in template_data:
                template.description = template_data["description"]
            if "variables" in template_data:
                template.variables = template_data["variables"]

            template.version = template.version + 1
            await session.commit()

            return {
                "id": str(template.id),
                "template_key": template.template_key,
                "name": template.name,
                "description": template.description,
                "template_type": template.template_type,
                "content": template.content,
                "variables": template.variables,
                "language": template.language,
                "version": template.version,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update template %s: %s", template_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update template: {str(e)}",
        )


@router.get("/print-settings")
async def get_print_settings(
    company_id: UUID | None = None,
):
    """Get current user/company print settings."""
    from sqlalchemy import select
    from src.infrastructure.database.models.print_settings import PrintSettings

    try:
        if not company_id:
            return {
                "header_text": "Valutazione Rischio Rumore - D.Lgs. 81/2008",
                "footer_text": "MARS DVR",
                "cover_title": "VALUTAZIONE RISCHIO RUMORE",
                "cover_subtitle": "Documento di Valutazione",
                "logo_url": None,
                "primary_color": "#1a365d",
                "secondary_color": "#2c5282",
                "font_family": "Times New Roman",
                "font_size": 12,
                "paper_size": "A4",
                "margins": {"top": 25, "bottom": 25, "left": 20, "right": 20},
            }

        async with get_db() as session:
            result = await session.execute(
                select(PrintSettings).where(PrintSettings.company_id == company_id)
            )
            settings = result.scalar_one_or_none()

            if not settings:
                return {
                    "header_text": "Valutazione Rischio Rumore - D.Lgs. 81/2008",
                    "footer_text": "MARS DVR",
                    "cover_title": "VALUTAZIONE RISCHIO RUMORE",
                    "cover_subtitle": "Documento di Valutazione",
                    "logo_url": None,
                    "primary_color": "#1a365d",
                    "secondary_color": "#2c5282",
                    "font_family": "Times New Roman",
                    "font_size": 12,
                    "paper_size": "A4",
                    "margins": {"top": 25, "bottom": 25, "left": 20, "right": 20},
                }

            return {
                "header_text": settings.header_text,
                "footer_text": settings.footer_text,
                "cover_title": settings.cover_title,
                "cover_subtitle": settings.cover_subtitle,
                "logo_url": settings.logo_url,
                "primary_color": settings.primary_color,
                "secondary_color": settings.secondary_color,
                "font_family": settings.font_family,
                "font_size": settings.font_size,
                "paper_size": settings.paper_size,
                "margins": settings.margins,
            }

    except Exception as e:
        logger.error("Failed to get print settings: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get print settings: {str(e)}",
        )


@router.put("/print-settings")
async def save_print_settings(
    company_id: UUID,
    settings_data: dict,
):
    """Save print settings."""
    from sqlalchemy import select
    from src.infrastructure.database.models.print_settings import PrintSettings

    try:
        async with get_db() as session:
            result = await session.execute(
                select(PrintSettings).where(PrintSettings.company_id == company_id)
            )
            settings = result.scalar_one_or_none()

            if settings:
                if "header_text" in settings_data:
                    settings.header_text = settings_data["header_text"]
                if "footer_text" in settings_data:
                    settings.footer_text = settings_data["footer_text"]
                if "cover_title" in settings_data:
                    settings.cover_title = settings_data["cover_title"]
                if "cover_subtitle" in settings_data:
                    settings.cover_subtitle = settings_data["cover_subtitle"]
                if "logo_url" in settings_data:
                    settings.logo_url = settings_data["logo_url"]
                if "primary_color" in settings_data:
                    settings.primary_color = settings_data["primary_color"]
                if "secondary_color" in settings_data:
                    settings.secondary_color = settings_data["secondary_color"]
                if "font_family" in settings_data:
                    settings.font_family = settings_data["font_family"]
                if "font_size" in settings_data:
                    settings.font_size = settings_data["font_size"]
                if "paper_size" in settings_data:
                    settings.paper_size = settings_data["paper_size"]
                if "margins" in settings_data:
                    settings.margins = settings_data["margins"]

                settings.version = settings.version + 1
            else:
                settings = PrintSettings(
                    company_id=company_id,
                    header_text=settings_data.get(
                        "header_text", "Valutazione Rischio Rumore"
                    ),
                    footer_text=settings_data.get("footer_text", "MARS DVR"),
                    cover_title=settings_data.get(
                        "cover_title", "VALUTAZIONE RISCHIO RUMORE"
                    ),
                    cover_subtitle=settings_data.get(
                        "cover_subtitle", "Documento di Valutazione"
                    ),
                    logo_url=settings_data.get("logo_url"),
                    primary_color=settings_data.get("primary_color", "#1a365d"),
                    secondary_color=settings_data.get("secondary_color", "#2c5282"),
                    font_family=settings_data.get("font_family", "Times New Roman"),
                    font_size=settings_data.get("font_size", 12),
                    paper_size=settings_data.get("paper_size", "A4"),
                    margins=settings_data.get(
                        "margins", {"top": 25, "bottom": 25, "left": 20, "right": 20}
                    ),
                )
                session.add(settings)

            await session.commit()

            return {
                "status": "ok",
                "company_id": str(company_id),
                "message": "Print settings saved successfully",
            }

    except Exception as e:
        logger.error("Failed to save print settings: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save print settings: {str(e)}",
        )
