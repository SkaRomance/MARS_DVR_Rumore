"""Add AI-related tables for interactions, suggestions, and narrative templates.

Revision ID: 005
Revises: 004
Create Date: 2026-04-08

Tables:
- ai_interaction: Log of all AI queries and responses
- ai_suggestion: AI-generated suggestions with approval workflow
- narrative_template: Configurable templates for DVR narrative sections
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_interaction",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=True),
        sa.Column("assessment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("interaction_type", sa.String(50), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_ai_interaction_company", "ai_interaction", ["company_id"])
    op.create_index("ix_ai_interaction_assessment", "ai_interaction", ["assessment_id"])
    op.create_index("ix_ai_interaction_type", "ai_interaction", ["interaction_type"])

    op.create_table(
        "ai_suggestion",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("assessment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("interaction_id", UUID(as_uuid=True), nullable=True),
        sa.Column("suggestion_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("risk_band", sa.String(20), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_ai_suggestion_assessment", "ai_suggestion", ["assessment_id"])
    op.create_index("ix_ai_suggestion_type", "ai_suggestion", ["suggestion_type"])
    op.create_index("ix_ai_suggestion_status", "ai_suggestion", ["status"])

    op.create_table(
        "narrative_template",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("template_key", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("template_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("variables", JSONB(), nullable=True),
        sa.Column("language", sa.String(5), server_default="it"),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_narrative_template_key", "narrative_template", ["template_key"])
    op.create_index("ix_narrative_template_active", "narrative_template", ["is_active"])
    op.create_index(
        "ix_narrative_template_category", "narrative_template", ["category"]
    )

    op.create_index("ix_ai_suggestion_interaction", "ai_suggestion", ["interaction_id"])


def downgrade():
    op.drop_table("ai_suggestion")
    op.drop_table("ai_interaction")
    op.drop_table("narrative_template")
