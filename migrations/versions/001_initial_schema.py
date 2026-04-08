"""Initial schema migration - creates all core tables.

Revision ID: 001
Revises:
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create ENUM types
    op.execute(
        "CREATE TYPE value_origin AS ENUM ('measured', 'calculated', 'estimated', 'imported', 'ai_suggested', 'validated', 'default_value')"
    )
    op.execute(
        "CREATE TYPE threshold_band AS ENUM ('negligible', 'low', 'medium', 'high', 'critical')"
    )
    op.execute(
        "CREATE TYPE action_type AS ENUM ('administrative', 'technical', 'ppe', 'medical', 'training', 'engineering')"
    )
    op.execute("CREATE TYPE entity_status AS ENUM ('active', 'inactive', 'archived')")

    # Company table
    op.create_table(
        "company",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ateco_primary_code", sa.String(10), nullable=True),
        sa.Column("fiscal_code", sa.String(16), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("status", sa.String(20), default="active"),
    )
    op.create_index("ix_company_ateco", "company", ["ateco_primary_code"])

    # NoiseAssessment table
    op.create_table(
        "noise_assessment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("unit_site_id", UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), default="active"),
        sa.Column("assessment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workers_count_exposed", sa.Integer(), default=0),
        sa.Column("representative_workers", sa.Text(), nullable=True),
        sa.Column("measurement_protocol", sa.String(255), nullable=True),
        sa.Column("instrument_class", sa.String(5), nullable=True),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("previous_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("_is_deleted", sa.Boolean(), default=False),
    )
    op.create_index("ix_noise_assessment_company", "noise_assessment", ["company_id"])
    op.create_index("ix_noise_assessment_status", "noise_assessment", ["status"])

    # NoiseAssessmentResult table
    op.create_table(
        "noise_assessment_result",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("assessment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_role_id", UUID(as_uuid=True), nullable=True),
        sa.Column("lex_8h", sa.Numeric(5, 1), nullable=True),
        sa.Column("lex_weekly", sa.Numeric(5, 1), nullable=True),
        sa.Column("lcpeak_db_c", sa.Numeric(5, 1), nullable=True),
        sa.Column("risk_band", sa.String(20), default="negligible"),
        sa.Column("uncertainty_db", sa.Numeric(4, 2), nullable=True),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("k_impulse", sa.Numeric(4, 1), default=0),
        sa.Column("k_tone", sa.Numeric(4, 1), default=0),
        sa.Column("k_background", sa.Numeric(4, 1), default=0),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_noise_assessment_result_lex", "noise_assessment_result", ["lex_8h"]
    )
    op.create_index(
        "ix_noise_assessment_result_assessment",
        "noise_assessment_result",
        ["assessment_id"],
    )

    # NoiseSourceCatalog table
    op.create_table(
        "noise_source_catalog",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("marca", sa.String(255), nullable=False),
        sa.Column("modello", sa.String(255), nullable=False),
        sa.Column("tipologia", sa.String(255), nullable=False),
        sa.Column("alimentazione", sa.String(100), nullable=True),
        sa.Column("laeq_min_db_a", sa.Numeric(5, 1), nullable=True),
        sa.Column("laeq_max_db_a", sa.Numeric(5, 1), nullable=True),
        sa.Column("laeq_typical_db_a", sa.Numeric(5, 1), nullable=True),
        sa.Column("lcpeak_db_c", sa.Numeric(5, 1), nullable=True),
        sa.Column(
            "fonte",
            sa.String(100),
            nullable=False,
            default="PAF - Portale Agenti Fisici",
        ),
        sa.Column("url_fonte", sa.String(500), nullable=True),
        sa.Column("data_aggiornamento", sa.Date(), nullable=False),
        sa.Column("disclaimer", sa.String(500), nullable=False),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("_is_deleted", sa.Boolean(), default=False),
    )
    op.create_index("ix_noise_source_catalog_marca", "noise_source_catalog", ["marca"])
    op.create_index(
        "ix_noise_source_catalog_tipologia", "noise_source_catalog", ["tipologia"]
    )

    # MachineAsset table
    op.create_table(
        "machine_asset",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("unit_site_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_catalog_id", UUID(as_uuid=True), nullable=True),
        sa.Column("marca", sa.String(255), nullable=False),
        sa.Column("modello", sa.String(255), nullable=False),
        sa.Column("matricola", sa.String(100), nullable=True),
        sa.Column("acquisition_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("_is_deleted", sa.Boolean(), default=False),
    )
    op.create_index("ix_machine_asset_company", "machine_asset", ["company_id"])

    # ATECO Catalog table
    op.create_table(
        "ateco_catalog",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(10), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("category", sa.String(5), nullable=True),
        sa.Column("section", sa.String(200), nullable=True),
        sa.Column("division", sa.String(10), nullable=True),
        sa.Column("group", sa.String(10), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_ateco_catalog_code", "ateco_catalog", ["code"])


def downgrade():
    op.drop_table("ateco_catalog")
    op.drop_table("machine_asset")
    op.drop_table("noise_source_catalog")
    op.drop_table("noise_assessment_result")
    op.drop_table("noise_assessment")
    op.drop_table("company")
    op.execute("DROP TYPE IF EXISTS entity_status")
    op.execute("DROP TYPE IF EXISTS action_type")
    op.execute("DROP TYPE IF EXISTS threshold_band")
    op.execute("DROP TYPE IF EXISTS value_origin")
