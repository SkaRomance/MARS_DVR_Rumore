"""Add auth and tenant tables, add tenant_id to existing tables.

Revision ID: 007
Revises: 006
Create Date: 2026-04-12

Tables:
- tenant: Multi-tenant organization
- user: Auth users with role-based access
Columns added:
- tenant_id (UUID, nullable) to: company, noise_assessment, noise_assessment_result,
  ai_interaction, ai_suggestion, job_role, mitigation_measure,
  assessment_document, document_template, print_settings
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "company",
    "noise_assessment",
    "noise_assessment_result",
    "ai_interaction",
    "ai_suggestion",
    "job_role",
    "mitigation_measure",
    "assessment_document",
    "document_template",
    "print_settings",
]


def upgrade():
    op.create_table(
        "tenant",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("keygen_account_id", sa.String(255), nullable=True),
        sa.Column("keygen_license_id", sa.String(255), nullable=True),
        sa.Column("license_status", sa.String(20), server_default="inactive"),
        sa.Column("logo_data", sa.LargeBinary(), nullable=True),
        sa.Column("logo_mime_type", sa.String(50), nullable=True),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("max_assessments", sa.Integer(), server_default="10"),
        sa.Column("license_activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("machine_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_slug", "tenant", ["slug"])

    op.create_table(
        "user",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(20), server_default="consultant"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_user_tenant_id", "user", ["tenant_id"])
    op.create_index("ix_user_email", "user", ["email"])
    op.create_foreign_key(
        "fk_user_tenant_id_tenant", "user", "tenant", ["tenant_id"], ["id"]
    )

    for table in TENANT_TABLES:
        op.add_column(
            table,
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        )
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.create_foreign_key(
            f"fk_{table}_tenant_id_tenant", table, "tenant", ["tenant_id"], ["id"]
        )


def downgrade():
    for table in TENANT_TABLES:
        op.drop_constraint(f"fk_{table}_tenant_id_tenant", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")

    op.drop_table("user")
    op.drop_table("tenant")