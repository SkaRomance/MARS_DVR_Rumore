"""Backfill tenant_id and add NOT NULL constraint, add tenant_id to missing tables.

Revision ID: 009
Revises: 008
Create Date: 2026-04-13

Steps:
1. Add tenant_id column to noise_source_catalog, machine_asset, narrative_template
   (these tables were added in migrations 003/005 but missed by 007)
2. Backfill all NULL tenant_id values with the first existing tenant
3. Alter all tenant_id columns to NOT NULL
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

NEW_TENANT_TABLES = [
    "noise_source_catalog",
    "machine_asset",
    "narrative_template",
]

ALL_TENANT_TABLES = [
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
    "noise_source_catalog",
    "machine_asset",
    "narrative_template",
]


def upgrade():
    for table in NEW_TENANT_TABLES:
        op.add_column(
            table,
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        )
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.create_foreign_key(
            f"fk_{table}_tenant_id_tenant", table, "tenant", ["tenant_id"], ["id"]
        )

    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM tenant ORDER BY created_at LIMIT 1"))
    row = result.fetchone()

    if row is not None:
        default_tenant_id = str(row[0])
        for table in ALL_TENANT_TABLES:
            conn.execute(
                sa.text(f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id IS NULL"),
                {"tid": default_tenant_id},
            )
    else:
        dummy_id = "00000000-0000-0000-0000-000000000000"
        for table in ALL_TENANT_TABLES:
            conn.execute(
                sa.text(f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id IS NULL"),
                {"tid": dummy_id},
            )

    for table in ALL_TENANT_TABLES:
        op.alter_column(table, "tenant_id", nullable=False)


def downgrade():
    for table in ALL_TENANT_TABLES:
        op.alter_column(table, "tenant_id", nullable=True)

    for table in NEW_TENANT_TABLES:
        op.drop_constraint(f"fk_{table}_tenant_id_tenant", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")
