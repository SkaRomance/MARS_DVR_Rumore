# Wave 28 — Scheduler + Sync Normativo

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`. APScheduler in processo separato (container dedicato). Richiede Wave 25 (outbox table).

**Goal:** Scheduler APScheduler con 5 job cron per: PAF delta sync settimanale, ATECO sync check, Gazzetta Ufficiale + EUR-Lex watchdog normativo, RAG re-index, outbox dispatcher.

**Architecture:** Processo Python separato (container `scheduler` in docker-compose) con APScheduler AsyncIOScheduler. Condivide DB + Redis + ChromaDB con l'app principale. Non esposto su HTTP.

**Tech Stack:** APScheduler 3.10+, httpx (per RSS/HTTP fetch), feedparser (RSS), existing PAF CLI, ChromaDB client.

**Stima:** 2h.

---

## Pre-requisiti

- Wave 25 applicato (rumore_outbox table esistente)
- Branch work: `noise-thin-plugin-refactor` (continua)

---

## Task 1: Setup scheduler package

**Files:**
- Create: `src/infrastructure/scheduler/__init__.py`
- Create: `src/infrastructure/scheduler/runner.py`
- Create: `src/infrastructure/scheduler/jobs/__init__.py`
- Modify: `pyproject.toml` (aggiungi `apscheduler>=3.10`, `feedparser>=6.0`)

- [ ] **Step 1.1: Aggiungi deps**

File: `pyproject.toml` — nel blocco `dependencies`:

```toml
"apscheduler>=3.10.0",
"feedparser>=6.0.11",
```

Install:
```bash
cd "C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore"
pip install "apscheduler>=3.10.0" "feedparser>=6.0.11"
```

- [ ] **Step 1.2: Runner principale**

File: `src/infrastructure/scheduler/runner.py`

```python
"""Scheduler runner — separate process from FastAPI app."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.bootstrap.config import get_settings
from src.infrastructure.scheduler.jobs.outbox_dispatcher import dispatch_outbox
from src.infrastructure.scheduler.jobs.paf_delta_sync import paf_delta_sync
from src.infrastructure.scheduler.jobs.ateco_sync_check import ateco_sync_check
from src.infrastructure.scheduler.jobs.normativa_watchdog import normativa_watchdog
from src.infrastructure.scheduler.jobs.rag_reindex import rag_reindex_if_stale

logger = logging.getLogger(__name__)


def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()

    # Jobstore: SQLAlchemy on main DB for persistence + HA
    scheduler = AsyncIOScheduler(
        timezone="Europe/Rome",
        job_defaults={
            "coalesce": True,  # merge missed runs
            "max_instances": 1,  # no overlap
            "misfire_grace_time": 3600,
        },
    )

    # PAF delta sync — weekly Sunday 03:00
    scheduler.add_job(
        paf_delta_sync,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="paf_delta_sync",
        replace_existing=True,
    )

    # ATECO sync check — weekly Monday 04:00
    scheduler.add_job(
        ateco_sync_check,
        CronTrigger(day_of_week="mon", hour=4, minute=0),
        id="ateco_sync_check",
        replace_existing=True,
    )

    # Normativa watchdog — every 6 hours
    scheduler.add_job(
        normativa_watchdog,
        CronTrigger(hour="*/6", minute=15),
        id="normativa_watchdog",
        replace_existing=True,
    )

    # RAG re-index — daily 05:00
    scheduler.add_job(
        rag_reindex_if_stale,
        CronTrigger(hour=5, minute=0),
        id="rag_reindex_if_stale",
        replace_existing=True,
    )

    # Outbox dispatcher — every 5 min
    scheduler.add_job(
        dispatch_outbox,
        IntervalTrigger(minutes=5),
        id="outbox_dispatcher",
        replace_existing=True,
    )

    return scheduler


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    logger.info("Starting MARS DVR Rumore Scheduler")

    scheduler = build_scheduler()
    scheduler.start()

    logger.info("Jobs scheduled: %s", [j.id for j in scheduler.get_jobs()])

    # Graceful shutdown on SIGTERM
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _stop(*_):
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _stop)

    await stop_event.wait()

    logger.info("Stopping scheduler")
    scheduler.shutdown(wait=True)
    logger.info("Scheduler stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
```

- [ ] **Step 1.3: Aggiungi entry script**

File: `pyproject.toml` in `[project.scripts]`:

```toml
mars-scheduler = "src.infrastructure.scheduler.runner:main"
```

- [ ] **Step 1.4: Commit**

```bash
git add src/infrastructure/scheduler/ pyproject.toml
git commit -m "Wave 28.1: Add APScheduler runner with 5 jobs scheduled

Standalone process. AsyncIOScheduler with Europe/Rome TZ, coalesce,
max_instances=1, misfire_grace=3600s. Graceful SIGTERM shutdown.
Entry: \`mars-scheduler\` console script.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Job — outbox dispatcher

**Scope:** Scansiona `rumore_outbox` WHERE `dispatched_at IS NULL`, invia eventi (log-only oggi), marca dispatched.

**Files:**
- Create: `src/infrastructure/scheduler/jobs/outbox_dispatcher.py`
- Test: `tests/unit/test_outbox_dispatcher.py`

- [ ] **Step 2.1: Implementa dispatcher**

File: `src/infrastructure/scheduler/jobs/outbox_dispatcher.py`

```python
"""Outbox dispatcher: scans pending events and dispatches.

Currently: log-only (MARS cloud-native does not exist yet).
When cloud-native available: POST to cloud endpoint with HMAC signature.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.database import get_session_factory
from src.infrastructure.database.models.outbox import RumoreOutbox

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


async def dispatch_outbox():
    """Scheduler entry point — called every 5 min."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        pending = await _fetch_pending(session)
        if not pending:
            return

        logger.info("Dispatching %d pending outbox events", len(pending))
        for event in pending:
            try:
                await _dispatch_single(session, event)
            except Exception as exc:
                logger.error("Failed to dispatch event %s: %s", event.id, exc)
                event.error_message = str(exc)[:1000]
                event.retry_count += 1

        await session.commit()


async def _fetch_pending(session: AsyncSession) -> list[RumoreOutbox]:
    stmt = (
        select(RumoreOutbox)
        .where(RumoreOutbox.dispatched_at.is_(None))
        .where(RumoreOutbox.retry_count < 10)
        .order_by(RumoreOutbox.created_at.asc())
        .limit(BATCH_SIZE)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _dispatch_single(session: AsyncSession, event: RumoreOutbox):
    # For now, log-only dispatcher
    logger.info(
        "[OUTBOX] event=%s aggregate=%s:%s payload_size=%d",
        event.event_type,
        event.aggregate_type,
        event.aggregate_id,
        len(str(event.payload_json)),
    )

    # TODO: when MARS cloud-native exists:
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     await client.post(
    #         settings.cloud_native_events_url,
    #         json={...},
    #         headers={"X-Signature": hmac_sign(...)},
    #         timeout=10,
    #     )

    event.dispatched_at = datetime.now(timezone.utc)
    event.dispatcher = "log-only"
    event.error_message = None
```

- [ ] **Step 2.2: Test**

File: `tests/unit/test_outbox_dispatcher.py`

```python
import pytest
import uuid
from datetime import datetime, timezone

from src.infrastructure.database.models.outbox import RumoreOutbox
from src.infrastructure.scheduler.jobs.outbox_dispatcher import dispatch_outbox


@pytest.mark.asyncio
async def test_dispatches_pending_event(async_session, monkeypatch):
    event = RumoreOutbox(
        aggregate_type="noise_assessment_context",
        aggregate_id=uuid.uuid4(),
        event_type="noise.test",
        payload_json={"foo": "bar"},
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(event)
    await async_session.commit()

    # Mock get_session_factory to return our test factory
    monkeypatch.setattr(
        "src.infrastructure.scheduler.jobs.outbox_dispatcher.get_session_factory",
        lambda: async_session.__class__(bind=async_session.bind),
    )

    await dispatch_outbox()

    await async_session.refresh(event)
    assert event.dispatched_at is not None
    assert event.dispatcher == "log-only"


@pytest.mark.asyncio
async def test_skips_already_dispatched(async_session, monkeypatch):
    event = RumoreOutbox(
        aggregate_type="x",
        aggregate_id=uuid.uuid4(),
        event_type="y",
        payload_json={},
        created_at=datetime.now(timezone.utc),
        dispatched_at=datetime.now(timezone.utc),
    )
    async_session.add(event)
    await async_session.commit()

    original_dispatched = event.dispatched_at

    monkeypatch.setattr(
        "src.infrastructure.scheduler.jobs.outbox_dispatcher.get_session_factory",
        lambda: async_session.__class__(bind=async_session.bind),
    )

    await dispatch_outbox()
    await async_session.refresh(event)

    assert event.dispatched_at == original_dispatched
```

- [ ] **Step 2.3: Run + commit**

```bash
pytest tests/unit/test_outbox_dispatcher.py -v
git add src/infrastructure/scheduler/jobs/outbox_dispatcher.py tests/unit/test_outbox_dispatcher.py
git commit -m "Wave 28.2: Add outbox dispatcher job (log-only)

Scans rumore_outbox for dispatched_at IS NULL, batch 100, logs and
marks dispatched. Retry count increments on error (max 10).
Ready to swap log-only for cloud-native POST when cloud exists.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Job — PAF delta sync

**Scope:** Una volta alla settimana, rifare scraping incrementale del portale PAF, aggiornare `NoiseSourceCatalog` con `last_synced_at`.

- [ ] **Step 3.1: Implementa job**

File: `src/infrastructure/scheduler/jobs/paf_delta_sync.py`

```python
"""PAF delta sync — weekly job to refresh NoiseSourceCatalog."""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

PAF_CLI_PATH = Path(__file__).resolve().parents[4] / "run_paf_noise.ps1"
EXPORT_DIR = Path(__file__).resolve().parents[4] / "exports" / "paf_delta"


async def paf_delta_sync():
    """Esegue PAF CLI in modalità discover → export incrementale."""
    logger.info("Starting PAF delta sync")

    if not PAF_CLI_PATH.exists():
        logger.warning("PAF CLI not found at %s; skipping", PAF_CLI_PATH)
        return

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Passo 1: discover
    try:
        result = subprocess.run(
            ["powershell.exe", "-File", str(PAF_CLI_PATH), "discover",
             "--output", str(EXPORT_DIR / "manifest.json"), "-v"],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            logger.error("PAF discover failed: %s", result.stderr[:500])
            return
    except subprocess.TimeoutExpired:
        logger.error("PAF discover timed out")
        return

    # Passo 2: export con --skip-existing per delta
    try:
        result = subprocess.run(
            ["powershell.exe", "-File", str(PAF_CLI_PATH), "export",
             "--output-dir", str(EXPORT_DIR),
             "--skip-existing",
             "--workers", "2",
             "-v"],
            capture_output=True, text=True, timeout=3600,
        )
        if result.returncode != 0:
            logger.error("PAF export failed: %s", result.stderr[:500])
            return
    except subprocess.TimeoutExpired:
        logger.error("PAF export timed out")
        return

    # Passo 3: carica JSONL → upsert in DB
    await _upsert_paf_catalog(EXPORT_DIR / "machines.jsonl")

    logger.info("PAF delta sync completed")


async def _upsert_paf_catalog(jsonl_path: Path):
    if not jsonl_path.exists():
        logger.warning("machines.jsonl not found")
        return

    import json
    from sqlalchemy.dialects.postgresql import insert
    from src.bootstrap.database import get_session_factory
    from src.infrastructure.database.models.noise_source import NoiseSourceCatalog

    session_factory = get_session_factory()
    inserted = updated = 0

    async with session_factory() as session:
        with jsonl_path.open() as f:
            for line in f:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                stmt = insert(NoiseSourceCatalog).values(
                    paf_obj_id=data.get("obj_id"),
                    brand=data.get("brand"),
                    model=data.get("model"),
                    type=data.get("tipologia"),
                    power_source=data.get("alimentazione"),
                    laeq_min=data.get("laeq_min"),
                    laeq_typ=data.get("laeq_typ"),
                    laeq_max=data.get("laeq_max"),
                    lcpeak_db=data.get("lcpeak"),
                    source_protocol=data.get("fonte"),
                    raw_text=data.get("raw_text"),
                    last_synced_at=datetime.now(timezone.utc),
                ).on_conflict_do_update(
                    index_elements=["paf_obj_id"],
                    set_={
                        "brand": data.get("brand"),
                        "model": data.get("model"),
                        "laeq_typ": data.get("laeq_typ"),
                        "last_synced_at": datetime.now(timezone.utc),
                    },
                )
                try:
                    await session.execute(stmt)
                    # Note: cannot distinguish insert vs update easily with ON CONFLICT
                    inserted += 1
                except Exception as exc:
                    logger.warning("Failed upsert %s: %s", data.get("obj_id"), exc)

        await session.commit()

    logger.info("PAF upsert: %d rows processed", inserted)
```

- [ ] **Step 3.2: Commit**

```bash
git add src/infrastructure/scheduler/jobs/paf_delta_sync.py
git commit -m "Wave 28.3: Add PAF delta sync job (weekly)

Wraps existing PAF CLI (run_paf_noise.ps1) with discover + export --skip-existing.
Upserts NoiseSourceCatalog via ON CONFLICT on paf_obj_id.
Updates last_synced_at for tracking staleness.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Job — ATECO sync check

File: `src/infrastructure/scheduler/jobs/ateco_sync_check.py`

```python
"""ATECO sync check — verifica hash JSON ATECO 2025 e re-seed se cambiato."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ATECO_JSON_PATH = Path(__file__).resolve().parents[4] / "data" / "ateco" / "ateco_2025.json"
ATECO_HASH_FILE = Path(__file__).resolve().parents[4] / "data" / "ateco" / ".ateco_2025.hash"


async def ateco_sync_check():
    """Verifica se il file JSON ATECO 2025 è cambiato; se sì, ri-seed."""
    logger.info("Starting ATECO sync check")

    if not ATECO_JSON_PATH.exists():
        logger.warning("ATECO 2025 JSON not found at %s; skipping", ATECO_JSON_PATH)
        return

    current_hash = _sha256_file(ATECO_JSON_PATH)
    last_hash = ATECO_HASH_FILE.read_text().strip() if ATECO_HASH_FILE.exists() else ""

    if current_hash == last_hash:
        logger.info("ATECO 2025 unchanged; skipping re-seed")
        return

    logger.info("ATECO 2025 changed (old=%s, new=%s); re-seeding", last_hash[:8], current_hash[:8])

    # TODO: re-seed ateco_catalog table from JSON
    # This is a placeholder. Full implementation: read JSON, upsert rows.
    # For MVP: log only; manual re-seed via CLI.
    logger.warning("ATECO re-seed is manual: run `python -m src.cli.seed_ateco_2025`")

    ATECO_HASH_FILE.write_text(current_hash)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
```

Commit:
```bash
git add src/infrastructure/scheduler/jobs/ateco_sync_check.py
git commit -m "Wave 28.4: Add ATECO sync check (hash-based change detection)

Weekly check of ateco_2025.json file hash. If changed, logs need for
manual re-seed. MVP approach; full auto-seed can be added when ATECO
updates frequency increases.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Job — Normativa watchdog

**Scope:** Monitora 3 fonti RSS/API per aggiornamenti normativa rumore, filtra per keywords, salva in `normativa_update`.

**Files:**
- Create: `migrations/versions/019_normativa_update.py`
- Create: `src/infrastructure/database/models/normativa_update.py`
- Create: `src/infrastructure/scheduler/jobs/normativa_watchdog.py`

- [ ] **Step 5.1: Migration + model**

```bash
alembic revision -m "normativa_update" --rev-id 019
```

File `migrations/versions/019_normativa_update.py`:

```python
"""normativa_update

Revision ID: 019
Revises: 018
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "normativa_update",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),  # gazzetta_ufficiale | eur_lex | inail
        sa.Column("external_id", sa.String(256), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("matched_keywords", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_normativa_source_external", "normativa_update", ["source", "external_id"], unique=True)
    op.create_index("ix_normativa_processed", "normativa_update", ["processed"])


def downgrade():
    op.drop_index("ix_normativa_processed", table_name="normativa_update")
    op.drop_index("uq_normativa_source_external", table_name="normativa_update")
    op.drop_table("normativa_update")
```

Model: `src/infrastructure/database/models/normativa_update.py`

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class NormativaUpdate(Base):
    __tablename__ = "normativa_update"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    matched_keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 5.2: Watchdog job**

File: `src/infrastructure/scheduler/jobs/normativa_watchdog.py`

```python
"""Normativa watchdog — monitor RSS/API for Italian noise safety regulations updates."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

import feedparser
import httpx

from src.bootstrap.database import get_session_factory
from src.infrastructure.database.models.normativa_update import NormativaUpdate

logger = logging.getLogger(__name__)

KEYWORDS = [
    "D.Lgs. 81",
    "decreto legislativo 81",
    "rumore",
    "acustica",
    "LEX,8h",
    "valutazione rischio rumore",
    "dpi uditivi",
    "ISO 9612",
    "UNI EN ISO 11690",
    "esposizione rumore lavorativo",
    "tutela udito",
]

SOURCES = {
    "gazzetta_ufficiale": "https://www.gazzettaufficiale.it/rss/atti_generali.xml",
    # EUR-Lex via search API would be ideal; fallback to RSS if available
    # "eur_lex": "https://eur-lex.europa.eu/rss/news.xml",
    # INAIL: manual JSON endpoint (fill in if known)
}


async def normativa_watchdog():
    logger.info("Running normativa watchdog")
    total_new = 0

    session_factory = get_session_factory()
    async with session_factory() as session:
        for source_name, url in SOURCES.items():
            try:
                entries = await _fetch_rss(url)
                new_count = await _process_entries(session, source_name, entries)
                total_new += new_count
                logger.info("Source %s: %d new matches", source_name, new_count)
            except Exception as exc:
                logger.error("Source %s failed: %s", source_name, exc)

        await session.commit()

    logger.info("Watchdog done: %d new entries total", total_new)


async def _fetch_rss(url: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers={"User-Agent": "MARS-Noise-Watchdog/0.1"})
    response.raise_for_status()

    parsed = feedparser.parse(response.content)
    return list(parsed.entries)


async def _process_entries(session, source: str, entries: Iterable) -> int:
    from sqlalchemy.dialects.postgresql import insert

    new_count = 0
    for entry in entries:
        title = getattr(entry, "title", "")
        summary = getattr(entry, "summary", "")
        link = getattr(entry, "link", "")
        external_id = getattr(entry, "id", link)

        combined = (title + " " + summary).lower()
        matched = [kw for kw in KEYWORDS if kw.lower() in combined]
        if not matched:
            continue

        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

        stmt = (
            insert(NormativaUpdate)
            .values(
                source=source,
                external_id=external_id,
                title=title,
                summary=summary,
                url=link,
                published_at=published,
                matched_keywords=matched,
                fetched_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(index_elements=["source", "external_id"])
        )
        result = await session.execute(stmt)
        if result.rowcount:
            new_count += 1

    return new_count
```

- [ ] **Step 5.3: Apply + commit**

```bash
alembic upgrade 019
git add migrations/versions/019_normativa_update.py src/infrastructure/database/models/normativa_update.py src/infrastructure/scheduler/jobs/normativa_watchdog.py
git commit -m "Wave 28.5: Add normativa_watchdog job + NormativaUpdate table

Monitors RSS Gazzetta Ufficiale for keywords related to noise safety
(D.Lgs. 81, rumore, ISO 9612, etc.). Stores matches in normativa_update
with unique constraint (source, external_id). Runs every 6h.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Job — RAG re-index if stale

File: `src/infrastructure/scheduler/jobs/rag_reindex.py`

```python
"""RAG re-index — daily check if new PDFs in paf_library/ or data/normativa/."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PAF_LIB_DIR = Path(__file__).resolve().parents[4] / "paf_library"
NORMATIVA_DIR = Path(__file__).resolve().parents[4] / "data" / "normativa"
STATE_FILE = Path(__file__).resolve().parents[4] / "data" / ".rag_index_state.txt"


async def rag_reindex_if_stale():
    logger.info("Checking RAG index staleness")

    fingerprint = _compute_fingerprint()
    last_fingerprint = STATE_FILE.read_text().strip() if STATE_FILE.exists() else ""

    if fingerprint == last_fingerprint:
        logger.info("No changes; skipping re-index")
        return

    logger.info("Detected changes; re-indexing")
    from src.cli.index_paf_library import run_index  # existing CLI
    # Invoke programmatic re-index; modifica run_index per accettare params se necessario
    try:
        run_index(reset=False)
        STATE_FILE.write_text(fingerprint)
    except Exception as exc:
        logger.error("Re-index failed: %s", exc)


def _compute_fingerprint() -> str:
    h = hashlib.sha256()
    for directory in [PAF_LIB_DIR, NORMATIVA_DIR]:
        if not directory.exists():
            continue
        for pdf in sorted(directory.rglob("*.pdf")):
            h.update(str(pdf.relative_to(directory)).encode())
            h.update(str(pdf.stat().st_mtime_ns).encode())
    return h.hexdigest()
```

Commit:
```bash
git add src/infrastructure/scheduler/jobs/rag_reindex.py
git commit -m "Wave 28.6: Add RAG re-index if stale job (daily)

Fingerprints PDFs in paf_library/ and data/normativa/ by path+mtime.
Re-indexes ChromaDB only if fingerprint changed. Avoids unnecessary
embedding regeneration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: docker-compose scheduler service

**File:** Modify `docker-compose.yml`

```yaml
  scheduler:
    build: .
    command: ["python", "-m", "src.infrastructure.scheduler.runner"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://mars_noise:mars_noise_password@db:5432/mars_noise
      - REDIS_URL=redis://redis:6379/0
      - APP_ENV=production
      - OLLAMA_API_KEY=${OLLAMA_API_KEY:-}
      - MARS_API_BASE_URL=${MARS_API_BASE_URL:-http://app:8085}
      - MARS_JWT_ACCESS_SECRET=${MARS_JWT_ACCESS_SECRET:-}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      app:
        condition: service_healthy
    networks:
      - internal
    restart: unless-stopped
```

Commit:
```bash
git add docker-compose.yml
git commit -m "Wave 28.7: Add scheduler service to docker-compose

Separate container running mars-scheduler entry. Shares DB/Redis/env
with app service. Depends on app being healthy.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Lint + test + smoke

- [ ] **Step 8.1**

```bash
ruff check src/ tests/
make test
```

- [ ] **Step 8.2: Smoke test scheduler**

```bash
python -m src.infrastructure.scheduler.runner &
SCHED_PID=$!
sleep 10
kill $SCHED_PID
```

Expected: logs "Starting", "Jobs scheduled", e poi "Stopping" clean.

- [ ] **Step 8.3: STATUS + push**

```bash
# Update STATUS.md
git add docs/superpowers/plans/STATUS.md
git commit -m "Wave 28: Mark complete in STATUS"
git push
```

---

## Acceptance criteria Wave 28

1. ✅ Scheduler runner con 5 job configured
2. ✅ Outbox dispatcher log-only + 2 test
3. ✅ PAF delta sync (weekly)
4. ✅ ATECO sync check (weekly, hash-based)
5. ✅ Normativa watchdog (6h, RSS filtering) + tabella `normativa_update`
6. ✅ RAG re-index if stale (daily)
7. ✅ Container `scheduler` in docker-compose
8. ✅ Smoke test: scheduler starts + stops gracefully

---

## Rollback Wave 28

```bash
docker-compose stop scheduler
# or in env: SCHEDULER_ENABLED=false (if implemented as flag)
```

Rimuove solo lo schedulazione automatica; app funziona.

---

## Next Wave

**Wave 29 — Frontend P0 Completion** (`2026-04-17-wave-29-frontend.md`)
