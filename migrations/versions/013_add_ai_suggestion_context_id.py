"""Add context_id FK + make assessment_id nullable on ai_suggestion.

Opens AISuggestion to W27+ MARS-bound workflow while preserving legacy
assessment_id column for W16-23 rows.

Revision ID: 013
Revises: 012
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # assessment_id is now nullable (new W27 rows bind via context_id instead)
    op.alter_column(
        "ai_suggestion",
        "assessment_id",
        existing_type=UUID(as_uuid=True),
        nullable=True,
    )

    op.add_column(
        "ai_suggestion",
        sa.Column(
            "context_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "noise_assessment_context.id",
                ondelete="CASCADE",
                name="fk_ai_suggestion_context_id_noise_assessment_context",
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_ai_suggestion_context_id",
        "ai_suggestion",
        ["context_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_suggestion_context_id", table_name="ai_suggestion")
    op.drop_column("ai_suggestion", "context_id")
    op.alter_column(
        "ai_suggestion",
        "assessment_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
    )
