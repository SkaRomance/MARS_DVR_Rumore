"""Add noise_assessment_context table.

Binds a Rumore working session to a MARS DVR document + revision.

Revision ID: 012
Revises: 011
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "noise_assessment_context",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("mars_dvr_document_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("mars_revision_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("mars_document_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("dvr_snapshot", JSONB, nullable=True),
        sa.Column("dvr_schema_version", sa.String(10), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="bootstrapped",
            index=True,
        ),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "mars_dvr_document_id",
            "mars_revision_id",
            name="uq_noise_assessment_context_tenant_doc_rev",
        ),
    )

    # Composite index for list-by-tenant queries ordered by recency
    op.create_index(
        "ix_noise_assessment_context_tenant_updated",
        "noise_assessment_context",
        ["tenant_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_noise_assessment_context_tenant_updated",
        table_name="noise_assessment_context",
    )
    op.drop_table("noise_assessment_context")
