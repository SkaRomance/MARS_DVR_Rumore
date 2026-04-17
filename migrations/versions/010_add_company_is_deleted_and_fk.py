"""Add _is_deleted to company and FK constraints on company_id.

Revision ID: 010
Revises: 009
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "company",
        sa.Column(
            "_is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")
        ),
    )

    op.create_index("ix_company__is_deleted", "company", ["_is_deleted"])

    op.execute("UPDATE company SET _is_deleted = FALSE WHERE _is_deleted IS NULL")

    op.create_foreign_key(
        "fk_noise_assessment_company_id",
        "noise_assessment",
        "company",
        ["company_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_job_role_company_id",
        "job_role",
        "company",
        ["company_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_machine_asset_company_id",
        "machine_asset",
        "company",
        ["company_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "fk_machine_asset_company_id", "machine_asset", type_="foreignkey"
    )
    op.drop_constraint("fk_job_role_company_id", "job_role", type_="foreignkey")
    op.drop_constraint(
        "fk_noise_assessment_company_id", "noise_assessment", type_="foreignkey"
    )

    op.drop_index("ix_company__is_deleted", table_name="company")
    op.drop_column("company", "_is_deleted")
