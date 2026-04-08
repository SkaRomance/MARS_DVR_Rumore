"""Seed ATECO catalog from JSON.

Revision ID: 002
Revises: 001
Create Date: 2026-04-08
"""

from alembic import op
import json
from pathlib import Path


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def load_ateco_data():
    """Load ATECO data from JSON file."""
    data_file = (
        Path(__file__).parent.parent.parent / "data" / "ateco" / "ateco2007_sample.json"
    )
    with open(data_file, "r", encoding="utf-8") as f:
        return json.load(f)


def upgrade():
    """Insert ATECO records."""
    data = load_ateco_data()
    inserted = 0

    for item in data:
        code = item["codice"]
        desc = item["descrizione"].replace("'", "''")
        cat = item.get("categoria") or ""
        sez = item.get("sezione") or ""

        op.execute(f"""
            INSERT INTO ateco_catalog (code, description, category, section)
            VALUES ('{code}', '{desc}', '{cat}', '{sez}')
            ON CONFLICT (code) DO UPDATE SET
                description = EXCLUDED.description,
                category = EXCLUDED.category,
                section = EXCLUDED.section
        """)
        inserted += 1

    print(f"Inserted/updated {inserted} ATECO records")


def downgrade():
    """Delete all ATECO records."""
    op.execute("DELETE FROM ateco_catalog")
