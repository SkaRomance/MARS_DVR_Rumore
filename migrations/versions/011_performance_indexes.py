"""Add performance indexes for frequently queried columns.

Revision ID: 011
Revises: 010
Create Date: 2026-04-17
"""

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_noise_assessment_tenant_id", "noise_assessment", ["tenant_id"], if_not_exists=True)
    op.create_index("ix_noise_assessment_company_id", "noise_assessment", ["company_id"], if_not_exists=True)
    op.create_index("ix_noise_assessment_status", "noise_assessment", ["status"], if_not_exists=True)
    op.create_index("ix_company_tenant_id", "company", ["tenant_id"], if_not_exists=True)
    op.create_index("ix_job_role_tenant_id", "job_role", ["tenant_id"], if_not_exists=True)
    op.create_index("ix_job_role_company_id", "job_role", ["company_id"], if_not_exists=True)
    op.create_index("ix_mitigation_measure_tenant_id", "mitigation_measure", ["tenant_id"], if_not_exists=True)
    op.create_index("ix_mitigation_measure_assessment_id", "mitigation_measure", ["assessment_id"], if_not_exists=True)
    op.create_index("ix_machine_asset_tenant_id", "machine_asset", ["tenant_id"], if_not_exists=True)
    op.create_index("ix_machine_asset_company_id", "machine_asset", ["company_id"], if_not_exists=True)
    op.create_index("ix_user_tenant_id", "user", ["tenant_id"], if_not_exists=True)
    op.create_index("ix_user_email", "user", ["email"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_user_email", table_name="user", if_exists=True)
    op.drop_index("ix_user_tenant_id", table_name="user", if_exists=True)
    op.drop_index("ix_machine_asset_company_id", table_name="machine_asset", if_exists=True)
    op.drop_index("ix_machine_asset_tenant_id", table_name="machine_asset", if_exists=True)
    op.drop_index("ix_mitigation_measure_assessment_id", table_name="mitigation_measure", if_exists=True)
    op.drop_index("ix_mitigation_measure_tenant_id", table_name="mitigation_measure", if_exists=True)
    op.drop_index("ix_job_role_company_id", table_name="job_role", if_exists=True)
    op.drop_index("ix_job_role_tenant_id", table_name="job_role", if_exists=True)
    op.drop_index("ix_company_tenant_id", table_name="company", if_exists=True)
    op.drop_index("ix_noise_assessment_status", table_name="noise_assessment", if_exists=True)
    op.drop_index("ix_noise_assessment_company_id", table_name="noise_assessment", if_exists=True)
    op.drop_index("ix_noise_assessment_tenant_id", table_name="noise_assessment", if_exists=True)
