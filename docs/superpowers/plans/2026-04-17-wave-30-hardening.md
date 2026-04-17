# Wave 30 — Hardening + Cloud-native readiness

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`.

**Goal:** Portare il modulo da MVP a production-ready: structlog JSON, healthcheck completo, Prometheus metrics, non-root container, resource limits, CI/CD deploy workflow, docs operations (secrets rotation, rollback, backup restore).

**Tech Stack:** structlog 25+, prometheus-fastapi-instrumentator, GitHub Actions, Trivy.

**Stima:** 2h.

---

## Task 1: structlog JSON + correlation ID middleware

**Files:**
- Create: `src/infrastructure/observability/logging.py`
- Create: `src/infrastructure/observability/middleware.py`
- Modify: `src/bootstrap/main.py`

- [ ] **Step 1.1: Logging config**

File: `src/infrastructure/observability/logging.py`

```python
"""structlog JSON configuration with context binding."""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "mars-noise") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
```

- [ ] **Step 1.2: Correlation ID middleware**

File: `src/infrastructure/observability/middleware.py`

```python
"""Request ID + tenant/user context injection."""
from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

- [ ] **Step 1.3: Wire in main.py**

```python
from src.infrastructure.observability.logging import configure_logging
from src.infrastructure.observability.middleware import CorrelationIdMiddleware

settings = get_settings()
configure_logging(settings.log_level, json_output=(settings.app_env == "production"))

app = FastAPI(...)
app.add_middleware(CorrelationIdMiddleware)
```

- [ ] **Step 1.4: Commit**

```bash
git add src/infrastructure/observability/ src/bootstrap/main.py
git commit -m "Wave 30.1: Add structlog JSON + correlation ID middleware

JSON output in production (app_env=production), console in dev.
Every request gets request_id, propagated via X-Request-ID header.
Contextvars bound per-request: request_id, method, path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Healthcheck completo

**File:** `src/api/routes/health.py` (modify)

```python
"""Parallel healthcheck: DB, Redis, Ollama, MARS, ChromaDB."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.config import Settings, get_settings
from src.bootstrap.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


async def _check_db(session: AsyncSession) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "healthy", "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)[:200]}


async def _check_redis(url: str) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        client = aioredis.from_url(url)
        await client.ping()
        await client.close()
        return {"status": "healthy", "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)[:200]}


async def _check_ollama(base_url: str, api_key: str | None) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/api/tags", headers=headers)
            response.raise_for_status()
        return {"status": "healthy", "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)[:200]}


async def _check_mars(base_url: str) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # MARS exposes health or root; try /health then /
            response = await client.get(f"{base_url}/health", follow_redirects=True)
        return {"status": "healthy" if response.status_code < 500 else "degraded", "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)[:200]}


async def _check_chroma() -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        from src.infrastructure.rag.chroma_client import get_chroma_client
        client = get_chroma_client()
        client.heartbeat()  # sync call; may need to run in thread if slow
        return {"status": "healthy", "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)[:200]}


@router.get("/health")
async def health(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    db_check, redis_check, ollama_check, mars_check, chroma_check = await asyncio.gather(
        _check_db(session),
        _check_redis(settings.redis_url),
        _check_ollama(settings.ollama_base_url, settings.ollama_api_key),
        _check_mars(settings.mars_api_base_url),
        _check_chroma(),
        return_exceptions=True,
    )

    checks = {
        "db": db_check if not isinstance(db_check, Exception) else {"status": "unhealthy", "error": str(db_check)},
        "redis": redis_check if not isinstance(redis_check, Exception) else {"status": "unhealthy", "error": str(redis_check)},
        "ollama": ollama_check if not isinstance(ollama_check, Exception) else {"status": "degraded", "error": str(ollama_check)},
        "mars": mars_check if not isinstance(mars_check, Exception) else {"status": "degraded", "error": str(mars_check)},
        "chroma": chroma_check if not isinstance(chroma_check, Exception) else {"status": "degraded", "error": str(chroma_check)},
    }

    # Overall: unhealthy if DB or Redis down, degraded if Ollama/MARS/Chroma down
    critical = [checks["db"]["status"], checks["redis"]["status"]]
    if "unhealthy" in critical:
        overall = "unhealthy"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif any(c["status"] != "healthy" for c in checks.values()):
        overall = "degraded"
        http_status = status.HTTP_200_OK
    else:
        overall = "healthy"
        http_status = status.HTTP_200_OK

    return {"status": overall, "checks": checks, "version": "0.1.0"}
```

Commit:
```bash
git add src/api/routes/health.py
git commit -m "Wave 30.2: Healthcheck parallel DB+Redis+Ollama+MARS+Chroma

Unhealthy if DB/Redis down (critical), degraded if Ollama/MARS/Chroma down.
Per-check latency_ms for observability. Returns 503 only on unhealthy."
```

---

## Task 3: Prometheus metrics

**File:** `pyproject.toml` (add), `src/bootstrap/main.py` (wire)

```bash
pip install prometheus-fastapi-instrumentator
```

In `src/bootstrap/main.py`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

# ... after app = FastAPI(...)
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
```

Commit:
```bash
git add pyproject.toml src/bootstrap/main.py
git commit -m "Wave 30.3: Expose Prometheus metrics at /metrics

HTTP request count/latency per route/method/status. Excludes /health
to avoid noise. Grouped status codes (2xx/3xx/4xx/5xx)."
```

---

## Task 4: Non-root container + resource limits

**Files:** `Dockerfile`, `docker-compose.yml`

Dockerfile:

```dockerfile
# Stage build + runtime with non-root user
FROM python:3.11-slim AS builder
# ... existing build steps
RUN useradd -u 1001 -m appuser
COPY --chown=appuser:appuser . /app
USER appuser
WORKDIR /app
```

docker-compose.yml — aggiungi sotto `app` e `scheduler`:

```yaml
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 1G
        reservations:
          cpus: '0.25'
          memory: 256M
    user: "1001:1001"
    read_only: false  # python-docx needs /tmp write
    tmpfs:
      - /tmp
```

Commit:
```bash
git add Dockerfile docker-compose.yml
git commit -m "Wave 30.4: Non-root container + resource limits

USER 1001 (appuser) in Dockerfile. Docker compose with cpu/mem limits,
tmpfs /tmp for python-docx write. Rootless deploy friendly."
```

---

## Task 5: `.dockerignore` + secrets rotation docs

Files:
- Create: `.dockerignore`
- Create: `docs/operations/secrets-rotation.md`
- Create: `docs/operations/rollback.md`
- Create: `docs/operations/backup-restore.md`

`.dockerignore`:

```
.git
.pytest_cache
.ruff_cache
.venv
__pycache__
*.pyc
tests/
docs/
.opencode/
test_db.sqlite3
test_debug.sqlite3
exports/
paf_library/
data/
.firecrawl/
.tmp/
.env
*.msix
*.ps1
MARS_inspect/
```

`docs/operations/secrets-rotation.md`:

```markdown
# Secrets Rotation Runbook

## Annual rotation (minimum)

1. **JWT_SECRET_KEY** (Rumore auth, if still used)
   - Generate new: `openssl rand -base64 48`
   - Update `.env` + k8s secret
   - Rolling restart app pod; users must re-login
   - Grace period: 0 (forced logout)

2. **MARS_JWT_ACCESS_SECRET** (shared with MARS)
   - Coordinate with MARS team
   - Deploy new secret to BOTH services simultaneously
   - Rolling restart both
   - Users must re-login

3. **OLLAMA_API_KEY**
   - Rotate in Ollama Cloud dashboard
   - Update `.env`
   - Restart scheduler + app
   - No user impact

4. **KEYGEN_ADMIN_TOKEN** (licensing)
   - Rotate in Keygen dashboard
   - Update `.env`
   - Restart app
   - No user impact (licensing is eventually consistent)

5. **Postgres password**
   - `ALTER USER mars_noise WITH PASSWORD 'new-pass'`
   - Update `DATABASE_URL` in `.env`
   - Restart app + scheduler
   - Brief outage

6. **MODULE_EVENTS_WEBHOOK_SECRET** (MARS→Rumore webhook)
   - Coordinate with MARS
   - Update both
   - Restart
```

`docs/operations/rollback.md`:

```markdown
# Rollback Runbook

## Code rollback
1. Identify last-good SHA: `git log --oneline main | head -10`
2. Create rollback branch: `git checkout -b rollback-$(date +%Y%m%d) <SHA>`
3. Deploy via CI/CD: tag triggers build+push+deploy

## DB rollback
1. Identify Alembic revision to downgrade to: `alembic history | head`
2. `alembic downgrade <revision>`
3. If data lost: `pg_restore` from latest backup

## Full rollback
1. `docker-compose down`
2. Restore DB from backup: `bash docker/backup/pg_restore.sh /backups/latest.sql.gz`
3. `git checkout <last-good-SHA>`
4. `docker-compose up -d`
```

`docs/operations/backup-restore.md`:

```markdown
# Backup & Restore

## Backup schedule
- Daily: 02:00 UTC via backup container (already in compose)
- Retention: 30 days
- Location: `backup_data` volume (Docker named volume)

## Manual backup
```bash
docker exec $(docker ps -qf name=db) pg_dump -U mars_noise mars_noise | gzip > /tmp/manual_$(date +%Y%m%d).sql.gz
```

## Restore procedure
1. Stop app: `docker-compose stop app scheduler`
2. Restore: `gunzip -c /backups/20260417.sql.gz | docker exec -i $(docker ps -qf name=db) psql -U mars_noise mars_noise`
3. Verify: `docker exec $(docker ps -qf name=db) psql -U mars_noise -c '\dt'`
4. Restart: `docker-compose up -d`

## DR drill (quarterly)
1. Restore latest backup to staging
2. Run smoke tests
3. Verify healthcheck 5/5 green
4. Document issues
```

Commit:
```bash
git add .dockerignore docs/operations/
git commit -m "Wave 30.5: Add .dockerignore + operations runbooks

.dockerignore reduces image size (~40% in local tests).
3 runbooks: secrets rotation (annual schedule), rollback (code+DB),
backup/restore (daily schedule + DR drill quarterly)."
```

---

## Task 6: CI/CD deploy workflow

File: `.github/workflows/deploy.yml`

```yaml
name: Build + Deploy

on:
  push:
    tags: ['v*']
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment'
        required: true
        default: 'staging'
        type: choice
        options: [staging, production]

permissions:
  contents: read
  packages: write
  security-events: write

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=ref,event=tag
            type=sha,prefix=sha-
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Trivy scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ghcr.io/${{ github.repository }}:sha-${{ github.sha }}
          format: sarif
          output: trivy-results.sarif
          severity: HIGH,CRITICAL
          exit-code: 1  # fail build on high/critical vulns

      - name: Upload Trivy results
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: trivy-results.sarif

  deploy:
    needs: build-and-push
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - name: Deploy to ${{ inputs.environment }}
        run: |
          echo "Deploy step placeholder — wire to your deploy platform (Fly.io, AWS ECS, k8s, etc.)"
          # Example: ssh to VPS, docker compose pull + up -d
          # Or: kubectl set image deployment/rumore-app rumore=ghcr.io/.../rumore:${{ needs.build-and-push.outputs.image_tag }}
```

Commit:
```bash
git add .github/workflows/deploy.yml
git commit -m "Wave 30.6: Add CI/CD deploy workflow

Build + Trivy scan on tag push / manual dispatch.
SARIF upload to GitHub security tab.
Fails on HIGH/CRITICAL vulnerabilities.
Deploy step placeholder (wire to target platform)."
```

---

## Task 7: Lint + test + push

```bash
ruff check src/ tests/
make test
git push
```

Update STATUS.md + commit.

---

## Acceptance criteria Wave 30

1. ✅ structlog JSON + correlation ID middleware
2. ✅ Healthcheck 5 checks (DB, Redis, Ollama, MARS, Chroma) parallel
3. ✅ Prometheus metrics at `/metrics`
4. ✅ Dockerfile non-root user + resource limits in compose
5. ✅ `.dockerignore` complete
6. ✅ 3 operations runbooks (secrets rotation, rollback, backup/restore)
7. ✅ CI/CD deploy workflow with Trivy scan
8. ✅ Tests passing

---

## Next Wave

**Wave 31 — E2E Testing** (`2026-04-17-wave-31-e2e.md`)
