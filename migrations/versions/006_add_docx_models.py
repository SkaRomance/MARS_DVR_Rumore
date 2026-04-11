"""Add DOCX-related tables for job roles, mitigation measures, document templates, print settings, and assessment documents.

Revision ID: 006
Revises: 005
Create Date: 2026-04-09

Tables:
- job_role: Job roles/mansioni with exposure data
- mitigation_measure: Technical/administrative/PPE measures
- document_template: Template overrides for DOCX generation
- print_settings: Company print configuration
- assessment_document: Versioned exported documents
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Boolean

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_role",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("exposure_level", sa.String(20), nullable=True),
        sa.Column("risk_band", sa.String(20), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("_is_deleted", Boolean(), server_default="false"),
    )
    op.create_index("ix_job_role_company", "job_role", ["company_id"])
    op.create_index("ix_job_role_exposure_level", "job_role", ["exposure_level"])
    op.create_index("ix_job_role_risk_band", "job_role", ["risk_band"])

    op.create_table(
        "mitigation_measure",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("assessment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="3"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("implementation_date", sa.Date(), nullable=True),
        sa.Column("cost_euro", sa.Numeric(10, 2), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("_is_deleted", Boolean(), server_default="false"),
    )
    op.create_index(
        "ix_mitigation_measure_assessment", "mitigation_measure", ["assessment_id"]
    )
    op.create_index("ix_mitigation_measure_type", "mitigation_measure", ["type"])
    op.create_index("ix_mitigation_measure_status", "mitigation_measure", ["status"])

    op.create_table(
        "document_template",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("template_key", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("template_type", sa.String(50), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("variables", JSONB(), nullable=True),
        sa.Column("language", sa.String(5), server_default="it"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), server_default="1"),
    )
    op.create_index("ix_document_template_key", "document_template", ["template_key"])
    op.create_index("ix_document_template_active", "document_template", ["is_active"])
    op.create_index("ix_document_template_type", "document_template", ["template_type"])
    op.create_index("ix_document_template_category", "document_template", ["category"])

    op.create_table(
        "print_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("header_text", sa.String(500), nullable=True),
        sa.Column("footer_text", sa.String(500), nullable=True),
        sa.Column("cover_title", sa.String(255), nullable=True),
        sa.Column("cover_subtitle", sa.String(255), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("primary_color", sa.String(7), server_default="#1a365d"),
        sa.Column("secondary_color", sa.String(7), server_default="#2c5282"),
        sa.Column("font_family", sa.String(100), server_default="Times New Roman"),
        sa.Column("font_size", sa.Integer(), server_default="12"),
        sa.Column("paper_size", sa.String(10), server_default="A4"),
        sa.Column(
            "margins",
            JSONB(),
            server_default=sa.text(
                '\'{"top": 25, "bottom": 25, "left": 20, "right": 20}\'::jsonb'
            ),
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), server_default="1"),
    )
    op.create_index("ix_print_settings_company", "print_settings", ["company_id"])

    op.create_table(
        "assessment_document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("assessment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("language", sa.String(5), server_default="it"),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("content_json", JSONB(), nullable=True),
        sa.Column("generated_by", sa.String(50), server_default="system"),
        sa.Column("reviewer_name", sa.String(255), nullable=True),
        sa.Column("review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("_is_deleted", Boolean(), server_default="false"),
    )
    op.create_index(
        "ix_assessment_document_assessment", "assessment_document", ["assessment_id"]
    )
    op.create_index("ix_assessment_document_format", "assessment_document", ["format"])
    op.create_index("ix_assessment_document_status", "assessment_document", ["status"])


def downgrade():
    op.drop_table("assessment_document")
    op.drop_table("print_settings")
    op.drop_table("document_template")
    op.drop_table("mitigation_measure")
    op.drop_table("job_role")
