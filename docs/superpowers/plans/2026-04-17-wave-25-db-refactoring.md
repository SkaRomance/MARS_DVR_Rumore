# Wave 25 — Rumore DB Refactoring (cloud-native foundations)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` inline. Questo wave modifica schema DB Rumore. Richiede backup + test downgrade.

**Goal:** Trasformare lo schema DB di Rumore da standalone (con duplicati MARS) a thin plugin cloud-native ready: UUID globali, outbox pattern, audit log unificato, entità Rumore-specifiche, soft delete universale.

**Architecture:** 7 migration Alembic (012-018), ciascuna atomica e reversibile. Nessuna perdita di dati: si migra, si testa rollback, si committa.

**Tech Stack:** Alembic 1.14+, SQLAlchemy 2.0 async, asyncpg, PostgreSQL 16, pytest + aiosqlite per test.

**Repo:** `C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore` (branch da creare)

**Stima:** 3h. Parallelo con Wave 24.

---

## Pre-requisiti

- Branch work: `noise-thin-plugin-refactor`
- PostgreSQL 16 locale attivo
- Backup del DB corrente
- Alembic `head` al 011 attualmente

---

## Task 1: Setup branch + backup

**Files:** nessun cambio file (solo git + pg_dump)

- [ ] **Step 1.1: Crea branch work**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore"
git checkout master
git pull origin master
git checkout -b noise-thin-plugin-refactor
```

- [ ] **Step 1.2: Verifica alembic head corrente**

```bash
alembic current
```

Expected: `011_performance_indexes (head)`.

- [ ] **Step 1.3: Backup DB locale (se in uso con dati)**

```bash
# Solo se DATABASE_URL punta a DB con dati reali
docker exec $(docker ps -qf "name=db") pg_dump -U mars_noise mars_noise > /tmp/mars_noise_pre_wave25.sql
ls -la /tmp/mars_noise_pre_wave25.sql
```

Per ambiente di test (SQLite `test_db.sqlite3`), semplice `cp test_db.sqlite3 test_db_backup.sqlite3`.

- [ ] **Step 1.4: Run baseline test**

```bash
make test
```

Annota numero di test passing. Expected: ~235 tests, nessuno fallito (eccetto RAG slow su Windows).

- [ ] **Step 1.5: Nessun commit necessario (solo setup)**

---

## Task 2 — Migration 012: UUID migration per entità noise-specifiche

**Razionale:** Cloud-native readiness. Entità che possono migrare al cloud devono avere UUID globali anziché int autoincrement.

**Scope:** Solo tabelle noise-specifiche che restano dopo refactoring. NON tocchiamo company/user/tenant perché verranno droppate in 016.

**Tabelle target:** `ai_interaction`, `ai_suggestion`, `assessment_document`, `mitigation_measure`, `job_role`, `noise_assessment`, `noise_assessment_result`, `noise_source_catalog`, `machine_asset`, `document_template`, `print_settings`, `narrative_template`.

**Files:**
- Create: `migrations/versions/012_uuid_migration.py`
- Test: `tests/unit/test_migration_012.py`

- [ ] **Step 2.1: Crea file migration**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore"
alembic revision -m "uuid_migration_noise_entities" --rev-id 012
```

Questo crea `migrations/versions/012_uuid_migration_noise_entities.py` (skeleton).

- [ ] **Step 2.2: Scrivi migration UP + DOWN**

Sostituisci contenuto del file generato con:

```python
"""uuid_migration_noise_entities

Revision ID: 012
Revises: 011
Create Date: 2026-04-17

Converte colonne `id` delle entit\u00e0 noise-specifiche da Integer a UUID.
Preserva dati esistenti via sidecar columns + trigger copia.

IMPORTANTE: migration lunga su DB grandi. Eseguire offline.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

# Tabelle con relativi FK da aggiornare
TABLES_TO_MIGRATE = [
    "ai_interaction",
    "ai_suggestion",
    "assessment_document",
    "mitigation_measure",
    "job_role",
    "noise_assessment",
    "noise_assessment_result",
    "noise_source_catalog",
    "machine_asset",
    "document_template",
    "print_settings",
    "narrative_template",
]


def upgrade():
    """
    Strategy:
    1. Add new column `id_uuid UUID DEFAULT gen_random_uuid()` to each table
    2. Populate id_uuid for existing rows (NOT NULL after)
    3. For each FK: add `*_uuid` sidecar, populate via JOIN on old int FK
    4. Drop old int id + FKs, rename *_uuid → id/fk_name
    5. Re-add PK + FK constraints on UUID columns
    """
    # Requires pgcrypto extension for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- Phase 1: Add UUID sidecar columns ---
    for table in TABLES_TO_MIGRATE:
        op.add_column(
            table,
            sa.Column("id_uuid", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        )
        op.create_index(f"ix_{table}_id_uuid", table, ["id_uuid"], unique=True)

    # --- Phase 2: Add FK sidecar columns ---
    # ai_interaction.assessment_id -> noise_assessment.id
    op.add_column("ai_interaction", sa.Column("assessment_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE ai_interaction ai
        SET assessment_uuid = na.id_uuid
        FROM noise_assessment na
        WHERE ai.assessment_id = na.id
    """)

    # ai_suggestion: assessment_id, interaction_id
    op.add_column("ai_suggestion", sa.Column("assessment_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("ai_suggestion", sa.Column("interaction_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE ai_suggestion s
        SET assessment_uuid = na.id_uuid,
            interaction_uuid = ai.id_uuid
        FROM noise_assessment na, ai_interaction ai
        WHERE s.assessment_id = na.id AND s.interaction_id = ai.id
    """)

    # assessment_document.assessment_id
    op.add_column("assessment_document", sa.Column("assessment_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE assessment_document d
        SET assessment_uuid = na.id_uuid
        FROM noise_assessment na
        WHERE d.assessment_id = na.id
    """)

    # mitigation_measure.assessment_id
    op.add_column("mitigation_measure", sa.Column("assessment_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE mitigation_measure m
        SET assessment_uuid = na.id_uuid
        FROM noise_assessment na
        WHERE m.assessment_id = na.id
    """)

    # job_role.assessment_id (se esiste FK; verifica schema reale)
    op.add_column("job_role", sa.Column("assessment_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE job_role j
        SET assessment_uuid = na.id_uuid
        FROM noise_assessment na
        WHERE j.assessment_id = na.id
    """)

    # noise_assessment_result.assessment_id
    op.add_column("noise_assessment_result", sa.Column("assessment_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE noise_assessment_result r
        SET assessment_uuid = na.id_uuid
        FROM noise_assessment na
        WHERE r.assessment_id = na.id
    """)

    # machine_asset.assessment_id, .source_id
    op.add_column("machine_asset", sa.Column("assessment_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("machine_asset", sa.Column("source_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE machine_asset ma
        SET assessment_uuid = na.id_uuid,
            source_uuid = ns.id_uuid
        FROM noise_assessment na, noise_source_catalog ns
        WHERE ma.assessment_id = na.id AND ma.source_id = ns.id
    """)

    # --- Phase 3: Drop old int FKs, id columns; rename UUID columns ---
    # ai_interaction
    op.drop_constraint("ai_interaction_assessment_id_fkey", "ai_interaction", type_="foreignkey")
    op.drop_column("ai_interaction", "assessment_id")
    op.alter_column("ai_interaction", "assessment_uuid", new_column_name="assessment_id")
    op.drop_constraint("ai_interaction_pkey", "ai_interaction", type_="primary")
    op.drop_column("ai_interaction", "id")
    op.alter_column("ai_interaction", "id_uuid", new_column_name="id", server_default=sa.text("gen_random_uuid()"))
    op.create_primary_key("ai_interaction_pkey", "ai_interaction", ["id"])

    # ai_suggestion
    op.drop_constraint("ai_suggestion_assessment_id_fkey", "ai_suggestion", type_="foreignkey")
    op.drop_constraint("ai_suggestion_interaction_id_fkey", "ai_suggestion", type_="foreignkey")
    op.drop_column("ai_suggestion", "assessment_id")
    op.drop_column("ai_suggestion", "interaction_id")
    op.alter_column("ai_suggestion", "assessment_uuid", new_column_name="assessment_id")
    op.alter_column("ai_suggestion", "interaction_uuid", new_column_name="interaction_id")
    op.drop_constraint("ai_suggestion_pkey", "ai_suggestion", type_="primary")
    op.drop_column("ai_suggestion", "id")
    op.alter_column("ai_suggestion", "id_uuid", new_column_name="id", server_default=sa.text("gen_random_uuid()"))
    op.create_primary_key("ai_suggestion_pkey", "ai_suggestion", ["id"])

    # Ripeti pattern per le altre 10 tabelle (assessment_document, mitigation_measure,
    # job_role, noise_assessment, noise_assessment_result, noise_source_catalog,
    # machine_asset, document_template, print_settings, narrative_template).
    # Per brevità, lo script completo li gestisce in un loop helper:
    _migrate_remaining_tables_up()

    # --- Phase 4: Re-add FKs with UUID references ---
    op.create_foreign_key(
        "ai_interaction_assessment_id_fkey",
        "ai_interaction", "noise_assessment",
        ["assessment_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "ai_suggestion_assessment_id_fkey",
        "ai_suggestion", "noise_assessment",
        ["assessment_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "ai_suggestion_interaction_id_fkey",
        "ai_suggestion", "ai_interaction",
        ["interaction_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "assessment_document_assessment_id_fkey",
        "assessment_document", "noise_assessment",
        ["assessment_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "mitigation_measure_assessment_id_fkey",
        "mitigation_measure", "noise_assessment",
        ["assessment_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "noise_assessment_result_assessment_id_fkey",
        "noise_assessment_result", "noise_assessment",
        ["assessment_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "machine_asset_assessment_id_fkey",
        "machine_asset", "noise_assessment",
        ["assessment_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "machine_asset_source_id_fkey",
        "machine_asset", "noise_source_catalog",
        ["source_id"], ["id"],
        ondelete="SET NULL",
    )


def _migrate_remaining_tables_up():
    """Helper: apply int->uuid pattern to remaining 10 tables."""
    for table in [
        "assessment_document",
        "mitigation_measure",
        "job_role",
        "noise_assessment",
        "noise_assessment_result",
        "noise_source_catalog",
        "document_template",
        "print_settings",
        "narrative_template",
    ]:
        # Drop old int PK
        op.drop_constraint(f"{table}_pkey", table, type_="primary")
        op.drop_column(table, "id")
        # Rename UUID sidecar -> id
        op.alter_column(table, "id_uuid", new_column_name="id", server_default=sa.text("gen_random_uuid()"))
        op.create_primary_key(f"{table}_pkey", table, ["id"])

    # Machine asset: rinomina anche le FK UUIDs
    op.drop_column("machine_asset", "assessment_id")
    op.drop_column("machine_asset", "source_id")
    op.alter_column("machine_asset", "assessment_uuid", new_column_name="assessment_id")
    op.alter_column("machine_asset", "source_uuid", new_column_name="source_id")

    # noise_assessment_result: rename assessment_uuid -> assessment_id (dopo drop vecchia)
    op.drop_column("noise_assessment_result", "assessment_id")
    op.alter_column("noise_assessment_result", "assessment_uuid", new_column_name="assessment_id")

    # altri FK rename analoghi (assessment_document, mitigation_measure, job_role)
    for table in ["assessment_document", "mitigation_measure", "job_role"]:
        op.drop_column(table, "assessment_id")
        op.alter_column(table, "assessment_uuid", new_column_name="assessment_id")


def downgrade():
    """
    Rollback: da UUID torna a int autoincrement.
    ATTENZIONE: perdita di mappatura ID tra vecchie e nuove — ogni row prenderà un nuovo int.
    Le FK vengono ricostruite on a best-effort basis.

    In produzione, preferire restore da backup pre-012.
    """
    raise NotImplementedError(
        "Downgrade for 012 is not implemented automatically. "
        "Restore from backup pre-wave25. If you really need to downgrade, "
        "contact Salvatore to write the int-rollback script."
    )
```

- [ ] **Step 2.3: Test migration apply + rollback simulated**

File: `tests/unit/test_migration_012.py`

```python
"""Test migration 012 apply + schema invariants."""
import pytest
from sqlalchemy import text
from alembic.config import Config
from alembic import command


@pytest.mark.asyncio
async def test_migration_012_adds_uuid_columns(engine):
    """After migration 012, all noise-specific tables have UUID id column."""
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "012")

    async with engine.connect() as conn:
        for table in [
            "ai_interaction",
            "ai_suggestion",
            "assessment_document",
            "noise_assessment",
        ]:
            result = await conn.execute(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = 'id'"
                ),
                {"t": table},
            )
            row = result.first()
            assert row is not None, f"Table {table} missing id column"
            assert row[0] == "uuid", f"Table {table}.id should be UUID, got {row[0]}"


@pytest.mark.asyncio
async def test_migration_012_fks_intact(engine):
    """All FK constraints re-created after migration."""
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "012")

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT tc.constraint_name
                FROM information_schema.table_constraints tc
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                  AND tc.table_name IN ('ai_interaction', 'ai_suggestion', 'assessment_document')
                ORDER BY tc.constraint_name
                """
            )
        )
        fks = [r[0] for r in result]
        assert "ai_interaction_assessment_id_fkey" in fks
        assert "ai_suggestion_assessment_id_fkey" in fks
```

- [ ] **Step 2.4: Esegui migration + test su DB di test**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore"
alembic upgrade 012
pytest tests/unit/test_migration_012.py -v
```

Expected: 2/2 PASS.

- [ ] **Step 2.5: Commit**

```bash
git add migrations/versions/012_uuid_migration_noise_entities.py tests/unit/test_migration_012.py
git commit -m "Wave 25.2: Migration 012 — UUID migration for noise entities

Converts int IDs to UUID for 12 noise-specific tables.
Strategy: add UUID sidecar, populate, drop int, rename, re-create FKs.
Cloud-native readiness: UUIDs enable cross-tenant/cross-app merge.

Downgrade: not automated (restore from backup instead).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — Migration 013: `rumore_outbox` table

**Scope:** Outbox pattern per cloud-native readiness. Ogni modifica entità Rumore emette evento; dispatcher (oggi log-only) consuma.

- [ ] **Step 3.1: Crea migration**

```bash
alembic revision -m "add_rumore_outbox" --rev-id 013
```

- [ ] **Step 3.2: Implementa up/down**

File: `migrations/versions/013_add_rumore_outbox.py`

```python
"""add_rumore_outbox

Revision ID: 013
Revises: 012
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rumore_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("payload_json", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatcher", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_outbox_pending", "rumore_outbox", ["dispatched_at"], postgresql_where=sa.text("dispatched_at IS NULL"))
    op.create_index("ix_outbox_aggregate", "rumore_outbox", ["aggregate_type", "aggregate_id"])
    op.create_index("ix_outbox_event_type", "rumore_outbox", ["event_type"])


def downgrade():
    op.drop_index("ix_outbox_event_type", table_name="rumore_outbox")
    op.drop_index("ix_outbox_aggregate", table_name="rumore_outbox")
    op.drop_index("ix_outbox_pending", table_name="rumore_outbox")
    op.drop_table("rumore_outbox")
```

- [ ] **Step 3.3: Crea model SQLAlchemy**

File: `src/infrastructure/database/models/outbox.py`

```python
"""Outbox pattern for cloud-native readiness."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class RumoreOutbox(Base):
    __tablename__ = "rumore_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatcher: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

- [ ] **Step 3.4: Test + upgrade**

```bash
alembic upgrade 013
pytest tests/unit/ -k "outbox" -v
```

Se nessun test esiste per outbox, aggiungi:

File: `tests/unit/test_outbox_model.py`

```python
import pytest
import uuid
from src.infrastructure.database.models.outbox import RumoreOutbox


@pytest.mark.asyncio
async def test_create_outbox_event(async_session):
    event = RumoreOutbox(
        aggregate_type="noise_assessment",
        aggregate_id=uuid.uuid4(),
        event_type="noise.assessment.created",
        payload_json={"foo": "bar"},
        created_at=__import__("datetime").datetime.utcnow(),
    )
    async_session.add(event)
    await async_session.commit()
    assert event.id is not None
    assert event.retry_count == 0
    assert event.dispatched_at is None
```

- [ ] **Step 3.5: Commit**

```bash
git add migrations/versions/013_add_rumore_outbox.py src/infrastructure/database/models/outbox.py tests/unit/test_outbox_model.py
git commit -m "Wave 25.3: Migration 013 — rumore_outbox table

Outbox pattern: aggregate_type+id, event_type, payload, created_at,
dispatched_at (null=pending), dispatcher, retry_count. Partial index
on pending events for fast scheduler scan.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — Migration 014: AuditLog unificato

**Scope:** Estende `audit_log` esistente (da 008) con: `source` enum, `before_json`, `after_json`, UUID id, `entity_type`/`entity_id`.

- [ ] **Step 4.1: Crea migration**

```bash
alembic revision -m "unified_audit_log" --rev-id 014
```

- [ ] **Step 4.2: Implementa**

File: `migrations/versions/014_unified_audit_log.py`

```python
"""unified_audit_log

Revision ID: 014
Revises: 013
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

AUDIT_SOURCE_VALUES = ("user", "ai_autopilot", "ai_agent", "system", "scheduler")
AUDIT_ACTION_VALUES = ("create", "update", "delete", "approve", "reject", "calculate", "export", "ai_run", "login", "logout")


def upgrade():
    # Create enums
    op.execute(f"CREATE TYPE audit_source AS ENUM {AUDIT_SOURCE_VALUES}")
    op.execute(f"CREATE TYPE audit_action AS ENUM {AUDIT_ACTION_VALUES}")

    # Rename old audit_log if needed, or extend
    # Strategy: add new columns + convert existing data + drop old

    # Step 1: Add new columns nullable first
    op.add_column("audit_log", sa.Column("source", sa.Enum(*AUDIT_SOURCE_VALUES, name="audit_source"), nullable=True))
    op.add_column("audit_log", sa.Column("before_json", postgresql.JSONB, nullable=True))
    op.add_column("audit_log", sa.Column("after_json", postgresql.JSONB, nullable=True))
    op.add_column("audit_log", sa.Column("entity_type", sa.String(64), nullable=True))
    op.add_column("audit_log", sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=True))

    # Step 2: Backfill existing rows
    # Default source = 'user' for existing entries
    op.execute("UPDATE audit_log SET source = 'user' WHERE source IS NULL")
    # Action string column -> enum (if currently string)
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'audit_log' AND column_name = 'action' AND data_type = 'text') THEN
            ALTER TABLE audit_log ALTER COLUMN action TYPE audit_action USING action::audit_action;
          END IF;
        END$$;
        """
    )

    # Step 3: Make required columns NOT NULL
    op.alter_column("audit_log", "source", nullable=False, server_default="user")

    # Step 4: Indexes
    op.create_index("ix_audit_entity", "audit_log", ["entity_type", "entity_uuid"])
    op.create_index("ix_audit_source", "audit_log", ["source"])
    op.create_index("ix_audit_created", "audit_log", ["created_at"])


def downgrade():
    op.drop_index("ix_audit_created", table_name="audit_log")
    op.drop_index("ix_audit_source", table_name="audit_log")
    op.drop_index("ix_audit_entity", table_name="audit_log")
    op.drop_column("audit_log", "entity_uuid")
    op.drop_column("audit_log", "entity_type")
    op.drop_column("audit_log", "after_json")
    op.drop_column("audit_log", "before_json")
    op.drop_column("audit_log", "source")
    op.execute("DROP TYPE IF EXISTS audit_action")
    op.execute("DROP TYPE IF EXISTS audit_source")
```

- [ ] **Step 4.3: Update model `audit_log.py`**

File: `src/infrastructure/database/models/audit_log.py` — aggiungi:

```python
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID

class AuditSource(str, Enum):
    USER = "user"
    AI_AUTOPILOT = "ai_autopilot"
    AI_AGENT = "ai_agent"
    SYSTEM = "system"
    SCHEDULER = "scheduler"

class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    CALCULATE = "calculate"
    EXPORT = "export"
    AI_RUN = "ai_run"
    LOGIN = "login"
    LOGOUT = "logout"

# Nel model AuditLog aggiungi:
source: Mapped[AuditSource] = mapped_column(SAEnum(AuditSource, name="audit_source"), nullable=False)
before_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
after_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
entity_uuid: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
```

- [ ] **Step 4.4: Test + upgrade**

```bash
alembic upgrade 014
pytest tests/unit/test_audit_log.py -v  # se esistono test
```

- [ ] **Step 4.5: Commit**

```bash
git add migrations/versions/014_unified_audit_log.py src/infrastructure/database/models/audit_log.py
git commit -m "Wave 25.4: Migration 014 — unified audit_log with source + before/after

Adds audit_source enum (user, ai_autopilot, ai_agent, system, scheduler),
audit_action enum, entity_type+uuid, before_json+after_json for compliance
traceability of AI vs user modifications.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — Migration 015: NoiseAssessmentContext + refactor NoiseAssessment

**Scope:** Aggiungi nuova tabella `noise_assessment_context` che rappresenta l'associazione tra DVR MARS e valutazione Rumore. Rinomina/estendi `noise_assessment` se necessario.

- [ ] **Step 5.1: Crea migration**

```bash
alembic revision -m "noise_assessment_context" --rev-id 015
```

- [ ] **Step 5.2: Implementa**

File: `migrations/versions/015_noise_assessment_context.py`

```python
"""noise_assessment_context

Revision ID: 015
Revises: 014

Aggiunge tabella per lega
re assessment Rumore a DVR MARS (thin plugin architecture).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TYPE noise_context_status AS ENUM "
        "('ai_drafting', 'draft', 'review', 'published', 'archived')"
    )
    op.execute(
        "CREATE TYPE ai_autopilot_status AS ENUM "
        "('pending', 'running', 'completed', 'failed')"
    )

    op.create_table(
        "noise_assessment_context",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("mars_dvr_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mars_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mars_revision_version", sa.Integer(), nullable=False),
        sa.Column("mars_tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mars_company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ateco_code", sa.String(16), nullable=True),
        sa.Column("status", sa.Enum("ai_drafting", "draft", "review", "published", "archived", name="noise_context_status"), server_default="ai_drafting", nullable=False),
        sa.Column("ai_autopilot_status", sa.Enum("pending", "running", "completed", "failed", name="ai_autopilot_status"), server_default="pending", nullable=False),
        sa.Column("ai_autopilot_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_autopilot_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_autopilot_error", sa.Text(), nullable=True),
        sa.Column("ai_overall_confidence", sa.Float(), nullable=True),
        sa.Column("locked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_noise_context_mars_revision", "noise_assessment_context", ["mars_revision_id"])
    op.create_index("ix_noise_context_mars_tenant", "noise_assessment_context", ["mars_tenant_id"])
    op.create_index("ix_noise_context_mars_company", "noise_assessment_context", ["mars_company_id"])
    op.create_index(
        "uq_noise_context_per_revision",
        "noise_assessment_context",
        ["mars_revision_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Aggiungi FK context_id a noise_assessment esistente (nullable prima,
    # NOT NULL dopo backfill in wave 26)
    op.add_column("noise_assessment", sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "noise_assessment_context_id_fkey",
        "noise_assessment", "noise_assessment_context",
        ["context_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint("noise_assessment_context_id_fkey", "noise_assessment", type_="foreignkey")
    op.drop_column("noise_assessment", "context_id")
    op.drop_index("uq_noise_context_per_revision", table_name="noise_assessment_context")
    op.drop_index("ix_noise_context_mars_company", table_name="noise_assessment_context")
    op.drop_index("ix_noise_context_mars_tenant", table_name="noise_assessment_context")
    op.drop_index("ix_noise_context_mars_revision", table_name="noise_assessment_context")
    op.drop_table("noise_assessment_context")
    op.execute("DROP TYPE IF EXISTS ai_autopilot_status")
    op.execute("DROP TYPE IF EXISTS noise_context_status")
```

- [ ] **Step 5.3: Crea model**

File: `src/infrastructure/database/models/noise_assessment_context.py`

```python
"""NoiseAssessmentContext: links Rumore module to a MARS DVR revision."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Enum as SAEnum, Float, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base


class NoiseContextStatus(str, enum.Enum):
    AI_DRAFTING = "ai_drafting"
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AIAutopilotStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class NoiseAssessmentContext(Base):
    __tablename__ = "noise_assessment_context"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mars_dvr_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mars_revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mars_revision_version: Mapped[int] = mapped_column(Integer, nullable=False)
    mars_tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mars_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    ateco_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[NoiseContextStatus] = mapped_column(
        SAEnum(NoiseContextStatus, name="noise_context_status"),
        default=NoiseContextStatus.AI_DRAFTING,
        nullable=False,
    )

    ai_autopilot_status: Mapped[AIAutopilotStatus] = mapped_column(
        SAEnum(AIAutopilotStatus, name="ai_autopilot_status"),
        default=AIAutopilotStatus.PENDING,
        nullable=False,
    )
    ai_autopilot_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_autopilot_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_autopilot_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_overall_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    locked_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 5.4: Registra in __init__.py**

File: `src/infrastructure/database/models/__init__.py`

```python
from src.infrastructure.database.models.noise_assessment_context import (
    NoiseAssessmentContext,
    NoiseContextStatus,
    AIAutopilotStatus,
)

# Aggiungi a __all__
```

- [ ] **Step 5.5: Test + upgrade**

```bash
alembic upgrade 015
```

- [ ] **Step 5.6: Commit**

```bash
git add migrations/versions/015_noise_assessment_context.py src/infrastructure/database/models/noise_assessment_context.py src/infrastructure/database/models/__init__.py
git commit -m "Wave 25.5: Migration 015 — NoiseAssessmentContext + status enums

New table links Rumore module to MARS DVR revision. Tracks AI Autopilot
lifecycle (pending/running/completed/failed), lock state, confidence.
Unique constraint: one context per MARS revision (soft-deleted excluded).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — Migration 016: Drop Company/Tenant/User duplicati

**⚠️ ATTENZIONE:** Migration distruttiva. Richiede backup verificato e plan di rollback.

**Condizione:** Wave 26 deve avere già rimosso ogni riferimento FK a company/tenant/user locali nel codice Python (sostituiti da `mars_*_id`). In pratica: questa migration si esegue solo DOPO che Wave 26 ha deprecato i riferimenti.

**Nota:** Se Wave 26 non è pronta, saltare a Task 7 e completare 016 più tardi.

- [ ] **Step 6.1: Verifica prerequisiti**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore"
grep -rn "from src.infrastructure.database.models.company import" src/ tests/
grep -rn "from src.infrastructure.database.models.user import" src/ tests/
grep -rn "from src.infrastructure.database.models.tenant import" src/ tests/
```

Se grep ritorna risultati (oltre a `__init__.py`), Wave 26 non è completa. Skip Task 6 per ora.

- [ ] **Step 6.2: Crea migration (se prerequisiti OK)**

```bash
alembic revision -m "drop_duplicate_entities" --rev-id 016
```

- [ ] **Step 6.3: Implementa**

File: `migrations/versions/016_drop_duplicate_entities.py`

```python
"""drop_duplicate_entities

Revision ID: 016
Revises: 015

Rimuove tabelle company/user/tenant locali (duplicate di MARS).
Dopo questa migration, Rumore usa solo mars_tenant_id/mars_company_id
come UUID logici senza FK fisica.

ATTENZIONE: Esegui SOLO dopo Wave 26 (code refactored per non usare
le tabelle locali).
"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    # Drop FK constraints referencing these tables first
    for fk in [
        ("noise_assessment", "noise_assessment_tenant_id_fkey"),
        ("noise_assessment", "noise_assessment_company_id_fkey"),
        ("audit_log", "audit_log_user_id_fkey"),
        ("audit_log", "audit_log_tenant_id_fkey"),
        ("ai_interaction", "ai_interaction_user_id_fkey"),
        ("assessment_document", "assessment_document_user_id_fkey"),
    ]:
        op.execute(
            f"ALTER TABLE {fk[0]} DROP CONSTRAINT IF EXISTS {fk[1]}"
        )

    # Drop columns that referenced them
    for table, col in [
        ("noise_assessment", "tenant_id"),
        ("noise_assessment", "company_id"),
    ]:
        # Mantieni le colonne ma rinomina a mars_* prefix (per retention per query)
        op.alter_column(table, col, new_column_name=f"mars_{col}")

    # Drop dependent tables in correct order
    op.drop_table("user_session")  # se esiste
    op.drop_table("user")
    op.drop_table("tenant_member")  # se esiste
    op.drop_table("tenant")
    op.drop_table("company")


def downgrade():
    raise NotImplementedError(
        "Downgrade 016 requires restoring the DB from backup before Wave 25. "
        "Re-creating the dropped tables without data is not useful."
    )
```

- [ ] **Step 6.4: Commit (senza eseguire fino a Wave 26 done)**

```bash
git add migrations/versions/016_drop_duplicate_entities.py
git commit -m "Wave 25.6: Migration 016 — drop duplicate Company/Tenant/User (pending Wave 26)

Removes tables duplicated from MARS. Rumore uses only mars_*_id UUIDs
as logical references. Must be applied AFTER Wave 26 code refactor.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

**IMPORTANTE:** NON eseguire `alembic upgrade 016` ora. Aspetta fine Wave 26.

---

## Task 7 — Migration 017: origin enums + AI autopilot fields

**Scope:** Aggiunge enum `exposure_origin` e campi `ai_suggestion_id`, `approved_by`, `approved_at` a tabelle fasi/risultati.

- [ ] **Step 7.1: Crea migration**

```bash
alembic revision -m "exposure_origin_ai_fields" --rev-id 017
```

- [ ] **Step 7.2: Implementa**

File: `migrations/versions/017_exposure_origin_ai_fields.py`

```python
"""exposure_origin_ai_fields

Revision ID: 017
Revises: 016
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None

ORIGIN_VALUES = (
    "measured",
    "declared",
    "estimated",
    "ai_suggested",
    "user_validated_ai",
    "imported",
    "default_value",
)


def upgrade():
    op.execute(f"CREATE TYPE exposure_origin AS ENUM {ORIGIN_VALUES}")

    # Aggiungi colonne a noise_assessment_result (ipotesi tabella fasi)
    # Se hai una tabella noise_exposure_phase separata, applica qui.
    # Altrimenti, adatta a noise_assessment_result.
    for table in ["noise_assessment_result"]:
        op.add_column(
            table,
            sa.Column(
                "laeq_origin",
                sa.Enum(*ORIGIN_VALUES, name="exposure_origin"),
                nullable=True,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "duration_origin",
                sa.Enum(*ORIGIN_VALUES, name="exposure_origin"),
                nullable=True,
            ),
        )
        op.add_column(table, sa.Column("ai_suggestion_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(table, sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))

    # FK a ai_suggestion
    op.create_foreign_key(
        "nar_ai_suggestion_id_fkey",
        "noise_assessment_result", "ai_suggestion",
        ["ai_suggestion_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("nar_ai_suggestion_id_fkey", "noise_assessment_result", type_="foreignkey")
    for col in ["approved_at", "approved_by", "ai_suggestion_id", "duration_origin", "laeq_origin"]:
        op.drop_column("noise_assessment_result", col)
    op.execute("DROP TYPE IF EXISTS exposure_origin")
```

- [ ] **Step 7.3: Update model**

In `src/infrastructure/database/models/noise_assessment.py` aggiungi enum + colonne:

```python
class ExposureOrigin(str, enum.Enum):
    MEASURED = "measured"
    DECLARED = "declared"
    ESTIMATED = "estimated"
    AI_SUGGESTED = "ai_suggested"
    USER_VALIDATED_AI = "user_validated_ai"
    IMPORTED = "imported"
    DEFAULT_VALUE = "default_value"

# nel model NoiseAssessmentResult:
laeq_origin: Mapped[Optional[ExposureOrigin]] = mapped_column(
    SAEnum(ExposureOrigin, name="exposure_origin"), nullable=True
)
duration_origin: Mapped[Optional[ExposureOrigin]] = mapped_column(
    SAEnum(ExposureOrigin, name="exposure_origin"), nullable=True
)
ai_suggestion_id: Mapped[Optional[uuid.UUID]] = mapped_column(
    UUID(as_uuid=True), ForeignKey("ai_suggestion.id", ondelete="SET NULL"), nullable=True
)
approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 7.4: Test + upgrade**

```bash
alembic upgrade 017
pytest tests/unit/ -k "origin" -v
```

- [ ] **Step 7.5: Commit**

```bash
git add migrations/versions/017_exposure_origin_ai_fields.py src/infrastructure/database/models/noise_assessment.py
git commit -m "Wave 25.7: Migration 017 — exposure_origin enum + AI fields

Adds origin tracking (measured/declared/estimated/ai_suggested/
user_validated_ai/imported/default_value) to exposure data.
Links results to ai_suggestion that generated them.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — Migration 018: soft delete universale `deleted_at`

**Scope:** Ogni tabella data-bearing ottiene colonna `deleted_at timestamptz NULL` + query helper app-side.

- [ ] **Step 8.1: Crea migration**

```bash
alembic revision -m "soft_delete_universal" --rev-id 018
```

- [ ] **Step 8.2: Implementa**

File: `migrations/versions/018_soft_delete_universal.py`

```python
"""soft_delete_universal

Revision ID: 018
Revises: 017
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None

SOFT_DELETE_TABLES = [
    "ai_interaction",
    "ai_suggestion",
    "assessment_document",
    "ateco_catalog",
    "document_template",
    "job_role",
    "machine_asset",
    "mitigation_measure",
    "narrative_template",
    "noise_assessment",
    "noise_assessment_result",
    "noise_source_catalog",
    "print_settings",
]


def upgrade():
    for table in SOFT_DELETE_TABLES:
        # Skip tables that already have deleted_at (check via information_schema)
        op.execute(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = '{table}' AND column_name = 'deleted_at'
              ) THEN
                ALTER TABLE {table} ADD COLUMN deleted_at TIMESTAMPTZ;
                CREATE INDEX ix_{table}_deleted_at ON {table}(deleted_at) WHERE deleted_at IS NULL;
              END IF;
            END$$;
            """
        )


def downgrade():
    for table in SOFT_DELETE_TABLES:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_deleted_at")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS deleted_at")
```

- [ ] **Step 8.3: Query helper per SoftDelete**

File: `src/infrastructure/database/soft_delete.py`

```python
"""Helpers for soft-delete queries."""
from datetime import datetime
from sqlalchemy import Select
from sqlalchemy.orm import Query


def exclude_deleted(stmt: Select, model) -> Select:
    """Add WHERE deleted_at IS NULL to a SELECT statement."""
    return stmt.where(model.deleted_at.is_(None))


def soft_delete(instance) -> None:
    """Mark instance as deleted without removing from DB."""
    instance.deleted_at = datetime.utcnow()
```

- [ ] **Step 8.4: Test + upgrade**

```bash
alembic upgrade 018
```

- [ ] **Step 8.5: Commit**

```bash
git add migrations/versions/018_soft_delete_universal.py src/infrastructure/database/soft_delete.py
git commit -m "Wave 25.8: Migration 018 — soft delete universal deleted_at

Adds deleted_at TIMESTAMPTZ column (with partial index on NULL) to
13 data-bearing tables. Helpers for query filters and soft-delete action.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9 — Test rollback (downgrade) migrations

**Scope:** Verifica che ogni migration sia reversibile (tranne 012 e 016 che sono documentate no-rollback).

- [ ] **Step 9.1: Test downgrade 018 → 017**

```bash
alembic downgrade 017
alembic upgrade 018
```

Expected: entrambi senza errori.

- [ ] **Step 9.2: Test downgrade 017 → 015 (salta 016 che è ancora su commit ma non applicata)**

```bash
alembic downgrade 015
alembic upgrade 017
```

- [ ] **Step 9.3: Test downgrade 015 → 013**

```bash
alembic downgrade 013
alembic upgrade 015
```

- [ ] **Step 9.4: Test downgrade 014 → 013**

```bash
alembic downgrade 013
alembic upgrade 014
```

- [ ] **Step 9.5: Verifica che non ci siano regressioni test**

```bash
make test
```

Expected: tutti i test passano. Annota eventuali fallimenti.

- [ ] **Step 9.6: Commit log test**

Nessun commit (verifica operativa).

---

## Task 10 — Update Pydantic schemas per nuove entità

**Scope:** Aggiungi schemi Pydantic per `NoiseAssessmentContext`, `RumoreOutbox`, audit log v2 in `src/api/schemas/`.

- [ ] **Step 10.1: Crea schema NoiseAssessmentContext**

File: `src/api/schemas/noise_context.py`

```python
"""Pydantic schemas for NoiseAssessmentContext."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.infrastructure.database.models.noise_assessment_context import (
    AIAutopilotStatus,
    NoiseContextStatus,
)


class NoiseAssessmentContextBase(BaseModel):
    mars_dvr_document_id: uuid.UUID
    mars_revision_id: uuid.UUID
    mars_revision_version: int
    mars_tenant_id: uuid.UUID
    mars_company_id: uuid.UUID
    ateco_code: Optional[str] = None


class NoiseAssessmentContextCreate(NoiseAssessmentContextBase):
    pass


class NoiseAssessmentContextUpdate(BaseModel):
    status: Optional[NoiseContextStatus] = None
    ai_autopilot_status: Optional[AIAutopilotStatus] = None
    ai_overall_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    locked_by_user_id: Optional[uuid.UUID] = None


class NoiseAssessmentContextRead(NoiseAssessmentContextBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: NoiseContextStatus
    ai_autopilot_status: AIAutopilotStatus
    ai_autopilot_started_at: Optional[datetime] = None
    ai_autopilot_completed_at: Optional[datetime] = None
    ai_autopilot_error: Optional[str] = None
    ai_overall_confidence: Optional[float] = None
    locked_by_user_id: Optional[uuid.UUID] = None
    locked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
```

- [ ] **Step 10.2: Commit**

```bash
git add src/api/schemas/noise_context.py
git commit -m "Wave 25.10: Add Pydantic schemas for NoiseAssessmentContext

Create/Update/Read DTOs with proper validation (confidence 0-1,
enum types, optional fields).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11 — Lint + test finali + push

- [ ] **Step 11.1: Lint**

```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore"
ruff check src/ tests/
ruff format --check src/ tests/
```

Expected: zero errori.

- [ ] **Step 11.2: Test completo**

```bash
make test
```

Expected: tutti passing (eccetto slow RAG su Windows, già noti).

- [ ] **Step 11.3: Alembic history sanity check**

```bash
alembic history --verbose | head -40
alembic current
```

Expected: head = 018 (o 017 se 016 pending Wave 26).

- [ ] **Step 11.4: Push**

```bash
git push -u origin noise-thin-plugin-refactor
```

- [ ] **Step 11.5: Aggiorna STATUS.md**

File: `docs/superpowers/plans/STATUS.md` (crealo se non esiste)

```markdown
# Implementation Status

Last updated: 2026-04-17

## Waves

- [x] Wave 24 — MARS modifications (branch: noise-module-integration, PR: #N)
- [x] Wave 25 — Rumore DB refactoring (branch: noise-thin-plugin-refactor, migrations 012-018)
  - [x] 012 UUID migration
  - [x] 013 rumore_outbox
  - [x] 014 unified audit_log
  - [x] 015 NoiseAssessmentContext
  - [ ] 016 drop duplicate entities (pending Wave 26)
  - [x] 017 exposure_origin + AI fields
  - [x] 018 soft_delete universal
- [ ] Wave 26 — MARS integration backend
- [ ] Wave 27 — AI Autopilot
- [ ] Wave 28 — Scheduler
- [ ] Wave 29 — Frontend
- [ ] Wave 30 — Hardening
- [ ] Wave 31 — E2E
```

- [ ] **Step 11.6: Commit STATUS**

```bash
git add docs/superpowers/plans/STATUS.md
git commit -m "Wave 25.11: Update STATUS.md after DB refactoring

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push
```

---

## Acceptance criteria Wave 25

1. ✅ Migrations 012-015, 017, 018 applicate su DB locale senza errori (016 committata ma non applicata)
2. ✅ Downgrade test ok per 014, 015, 017, 018
3. ✅ Modelli SQLAlchemy aggiornati (NoiseAssessmentContext, RumoreOutbox, AuditSource/Action enums, ExposureOrigin)
4. ✅ Pydantic schemas per NoiseAssessmentContext
5. ✅ `make test` passing
6. ✅ `ruff check` passing
7. ✅ Branch `noise-thin-plugin-refactor` pushato
8. ✅ STATUS.md aggiornato

---

## Rollback Wave 25

```bash
# Se necessario undo:
alembic downgrade 011
# Restore da backup pre-wave:
psql -U mars_noise mars_noise < /tmp/mars_noise_pre_wave25.sql
git reset --hard master
git branch -D noise-thin-plugin-refactor
git push origin --delete noise-thin-plugin-refactor  # se pushato
```

---

## Next Wave

Dopo Wave 25 done, procedere con:
**Wave 26 — MARS Integration backend** (`2026-04-17-wave-26-mars-integration.md`)

Nota: Wave 26 richiede che Wave 24.1-24.5 siano completati (endpoint `/me`, JWT tenant_id, `/modules/.../verify`, PUT module-extensions).
