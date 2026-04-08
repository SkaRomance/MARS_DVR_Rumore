"""Seed noise source catalog from PAF data.

Revision ID: 003
Revises: 002
Create Date: 2026-04-08

Note: PAF data used for finalità prevenzione/sicurezza lavoro per D.Lgs. 81/2008.
"""

from alembic import op
import json
from pathlib import Path


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def load_noise_sources():
    """Load noise source data from JSON file."""
    data_file = (
        Path(__file__).parent.parent.parent
        / "data"
        / "knowledge_base"
        / "kb_sample.json"
    )
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("records", [])


def upgrade():
    """Insert noise source records from PAF."""
    sources = load_noise_sources()
    inserted = 0

    for src in sources:
        op.execute(f"""
            INSERT INTO noise_source_catalog (
                id, marca, modello, tipologia, alimentazione,
                laeq_min_db_a, laeq_max_db_a, laeq_typical_db_a,
                lcpeak_db_c, fonte, url_fonte,
                data_aggiornamento, disclaimer
            ) VALUES (
                '{src["id"]}',
                '{src["marca"]}',
                '{src["modello"]}',
                '{src["tipologia"]}',
                '{src.get("alimentazione", "")}',
                {src.get("laeq_min_db_a") or "NULL"},
                {src.get("laeq_max_db_a") or "NULL"},
                {src.get("laeq_typical_db_a") or "NULL"},
                {src.get("lcpeak_db_c") or "NULL"},
                '{src["fonte"]}',
                '{src.get("url_fonte", "")}',
                '{src["data_aggiornamento"]}',
                '{src["disclaimer"]}'
            )
            ON CONFLICT (id) DO UPDATE SET
                laeq_typical_db_a = EXCLUDED.laeq_typical_db_a,
                data_aggiornamento = EXCLUDED.data_aggiornamento
        """)
        inserted += 1

    print(f"Inserted/updated {inserted} noise source records from PAF")


def downgrade():
    """Delete PAF noise source records."""
    op.execute("DELETE FROM noise_source_catalog WHERE fonte LIKE '%PAF%'")
