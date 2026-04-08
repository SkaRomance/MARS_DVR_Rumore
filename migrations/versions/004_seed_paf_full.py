"""Seed full PAF noise source catalog.

Revision ID: 004
Revises: 003
Create Date: 2026-04-08

Loads all ~2,452 machines from the full PAF database.
For each machine, extracts all measurement records (lavoro/l_pa/incertezza).

Note: PAF data used for finalità prevenzione/sicurezza lavoro per D.Lgs. 81/2008.
Commercial use prohibited. See https://www.portaleagentifisici.it/
"""

import re
import uuid
from pathlib import Path
from typing import Any

from alembic import op
import json


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

PAF_JSON = (
    Path(__file__).parent.parent.parent
    / "data"
    / "knowledge_base"
    / "paf_full_2026-04-08.json"
)


def _parse_db_value(raw: str) -> float | None:
    """Parse '84.9 dBA' -> 84.9"""
    if not raw:
        return None
    m = re.search(r"([\d.]+)", str(raw).strip())
    return float(m.group(1)) if m else None


def _load_paf() -> list[dict[str, Any]]:
    with open(PAF_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("records", [])


def _iter_measurements(machine: dict[str, Any]):
    """Yield (lavoro, l_pa, incertezza) for each measurement record."""
    for m in machine.get("misure", []):
        l_pa = _parse_db_value(m.get("l_pa", ""))
        incertezza = _parse_db_value(m.get("incertezza", ""))
        lavoro = m.get("lavoro", "").strip()
        if l_pa is not None:
            yield lavoro, l_pa, incertezza


def upgrade():
    """Insert all PAF noise sources with their measurement variants.

    Each PAF machine may have multiple 'misure' (different working conditions).
    We store each as a separate catalog row with the same PAF id + a suffix.
    """
    machines = _load_paf()
    total = 0
    skipped = 0

    for machine in machines:
        paf_id = str(machine.get("id", "")).strip()
        marca = str(machine.get("marca", "")).strip()
        modello = str(machine.get("modello", "")).strip()
        tipologia = str(machine.get("tipologia", "")).strip()
        alimentazione = str(machine.get("alimentazione", "")).strip()
        url = str(machine.get("url", "")).strip()

        measurements = list(_iter_measurements(machine))
        if not measurements:
            skipped += 1
            continue

        if len(measurements) == 1:
            lavoro, l_pa, incertezza = measurements[0]
            _insert_row(
                paf_id=paf_id,
                marca=marca,
                modello=modello,
                tipologia=tipologia,
                alimentazione=alimentazione,
                l_pa=l_pa,
                incertezza=incertezza,
                lavoro=lavoro,
                url=url,
            )
            total += 1
        else:
            for idx, (lavoro, l_pa, incertezza) in enumerate(measurements, start=1):
                _insert_row(
                    paf_id=f"{paf_id}_{idx}",
                    marca=marca,
                    modello=modello,
                    tipologia=tipologia,
                    alimentazione=alimentazione,
                    l_pa=l_pa,
                    incertezza=incertezza,
                    lavoro=lavoro,
                    url=url,
                )
                total += 1

    print(
        f"Inserted {total} noise source records ({skipped} machines skipped, no l_pa)"
    )


def _insert_row(
    paf_id: str,
    marca: str,
    modello: str,
    tipologia: str,
    alimentazione: str,
    l_pa: float,
    incertezza: float | None,
    lavoro: str,
    url: str,
):
    """Insert a single row into noise_source_catalog."""
    laeq_typical = l_pa
    disclaimer = (
        "Dati per finalità prevenzione sicurezza lavoro - PAF Portale Agenti Fisici. "
        "Uso limitato a D.Lgs. 81/2008. vedi https://www.portaleagentifisici.it/"
    )

    # Escape single quotes
    marca = marca.replace("'", "''")[:255]
    modello = modello.replace("'", "''")[:255]
    tipologia = tipologia.replace("'", "''")[:255]
    alimentazione = alimentazione.replace("'", "''")[:100]
    disclaimer = disclaimer.replace("'", "''")[:500]
    url = url[:500]

    op.execute(f"""
        INSERT INTO noise_source_catalog (
            id, marca, modello, tipologia, alimentazione,
            laeq_min_db_a, laeq_max_db_a, laeq_typical_db_a,
            lcpeak_db_c, fonte, url_fonte,
            data_aggiornamento, disclaimer
        ) VALUES (
            '{uuid.uuid4()}',
            '{marca}',
            '{modello}',
            '{tipologia}',
            '{alimentazione}',
            NULL, NULL, {laeq_typical},
            NULL,
            'PAF - Portale Agenti Fisici',
            '{url}',
            CURRENT_DATE,
            '{disclaimer}'
        )
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    """Delete all PAF noise source records."""
    op.execute("DELETE FROM noise_source_catalog WHERE fonte LIKE '%PAF%'")
