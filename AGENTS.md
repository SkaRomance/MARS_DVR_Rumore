# MARS DVR Rumore — Project Context for AI Agents

## LSP-Type Tools (pyright)
Pyright v1.1.408 is installed. Use for type-checking instead of Serena LSP:
```bash
# Type-check a single file
pyright src/api/routes/assessments.py

# Type-check specific modules
pyright src/infrastructure/auth/

# Full project type-check
pyright src/

# JSON output for parsing
pyright --outputjson src/api/routes/auth_routes.py
```

## What This Is
B2B SaaS module for occupational noise risk assessment (D.Lgs. 81/2008). Backend: FastAPI + Vanilla JS frontend + AI (Ollama GLM-5.1:cloud) + RAG (ChromaDB).

## Quick Start
```bash
python -m uvicorn src.bootstrap.main:app --host 0.0.0.0 --port 8085
python -m pytest tests/ -k "not slow" --tb=short -q
python -m src.cli.create_admin --name "X" --slug "x" --email "a@b.com" --password "Pw"
```

## Critical Patterns (MUST FOLLOW)

### Database & Routes
- ALL route files use `db: AsyncSession = Depends(get_db)` — NEVER `async with get_db() as session:`
- Company uses `_is_deleted` (bool), NOT `status = archived`
- Tenant isolation: all CRUD routes filter by `tenant_id == tenant.id`
- SQLAlchemy `.where(Model._is_deleted == False)` requires `== False` (not Python `not`) — ruff E712 is ignored for this

### Schemas & Pydantic V2
- `X | None` without `default=None` is REQUIRED, not Optional
- EmailStr rejects reserved TLDs (.local, .test, .localhost) — use .com
- `validate_password_policy()`: min 8 char + 1 uppercase + 1 lowercase + 1 digit

### Auth & Security
- UserRole enum values: lowercase (`admin`, `consultant`, `viewer`)
- EntityStatus: `active`, `inactive`, `archived`
- ThresholdBand: `negligible`, `low`, `medium`, `high`, `critical`
- ActionType: `administrative`, `technical`, `ppe`, `medical`, `training`, `engineering`
- Redis fallback: if unavailable, rate limiter returns `lambda: True`
- JWT `exp` claim: integer epoch, NOT datetime — use `datetime.fromtimestamp(payload["exp"], tz=timezone.utc)`
- JWT secret: default `""`, validator blocks boot in production if empty/equals `"change-me-in-production"`

### AI & RAG
- 6 AI agents: Bootstrap, Review, Explain, Narrative, Mitigation, SourceDetection
- AI agent imports are DYNAMIC (inside handler function) — mock path: `patch("src.domain.services.agents.<agent_module>.<AgentClass>.<method>", ...)`
- RAG `build_context` is SYNC (not async) — mock with `MagicMock`, NOT `AsyncMock`
- Ollama Cloud API: `/v1/chat/completions` works, `/v1/embeddings` returns 404 (RAG uses ChromaDB built-in)
- ChromaDB: 19,915 chunks indexed (3664 pages, 31 PDFs, 15 HSE categories)

### Frontend
- Vanilla JS (no framework), loaded from `static/`
- `authService.fetchWithAuth()` handles 401 → refresh token → retry
- Pydantic errors: `err.detail` can be array of objects — handle with `Array.isArray(err.detail) ? err.detail.map(e => e.msg).join(', ') : err.detail`
- FastAPI 307 redirect on trailing slash loses Authorization header — use exact path with/without slash as defined in router

### Testing
- SQLite tests: `PRAGMA foreign_keys=OFF`, conftest does `_replace_pg_types_with_sqlite()`
- Test AI: mock each agent individually with `patch("src.domain.services.agents.<module>.<Class>.<method>", new_callable=AsyncMock)`
- Fast tests: `python -m pytest tests/ -k "not slow"`

## API Endpoints (70 total, base: /api/v1/noise)

### Auth (/auth) — 5 endpoints
POST /auth/login, /auth/refresh, /auth/register (admin-only) | GET/PUT /auth/me

### Assessments (root) — 6 endpoints
POST / (create, require_license) | GET / (list) | GET /{id} | PUT /{id} | DELETE /{id} (soft) | POST /calculate

### Companies (/companies) — 5 endpoints
POST / | GET / | GET /{id} | PUT /{id} | DELETE /{id} (soft)

### Job Roles (/job-roles) — 5 endpoints
POST / | GET / (filter by company_id) | GET /{id} | PUT /{id} | DELETE /{id} (soft)

### Mitigations (/mitigations) — 5 endpoints
POST / | GET / (filter by assessment_id) | GET /{id} | PUT /{id} | DELETE /{id} (soft)

### Machine Assets (/machine-assets) — 5 endpoints
POST / | GET / (filter by company_id) | GET /{id} | PUT /{id} | DELETE /{id} (soft)

### Noise Source Catalog (/catalog) — 3 endpoints
GET / (filter tipologia, marca, min/max laeq) | GET /stats | GET /{id}

### ATECO (/ateco) — 3 endpoints
GET /macro-categories | GET /macro-categories/{code} | GET /code/{ateco_code}

### AI (/assessments/{id}/ai/) — 10 endpoints
GET /ai/health | POST .../ai/bootstrap | .../ai/review | .../ai/explain | .../ai/narrative | .../ai/suggest-mitigations | .../ai/detect-sources | GET .../ai/suggestions | POST .../ai/suggestions/{id}/action | GET .../ai/interactions

### Export (/export) — 12 endpoints
POST .../json | POST .../docx | GET .../preview | GET .../document | GET .../document/sections | GET/PUT .../document/sections/{section_id} | GET /templates | GET /templates/{id} | PUT /templates/{id} | GET/PUT /print-settings

### Admin (/admin) — 4 endpoints
POST/GET/DELETE /admin/tenant/logo | GET /admin/tenant

### License (/license) — 4 endpoints
POST /activate | POST /deactivate | GET /status | GET /usage

### RAG (/rag) — 3 endpoints
POST /query | POST /index (admin) | GET /stats

## Database Models (14 tables)
Tenant, User, Company, AtecoCatalog, JobRole, NoiseAssessment, NoiseAssessmentResult, NoiseSourceCatalog, MachineAsset, MitigationMeasure, DocumentTemplate, NarrativeTemplate, PrintSettings, AssessmentDocument, AuditLog, AIInteraction, AISuggestion

### Key relationships
- Company has many: NoiseAssessment, JobRole, MachineAsset, PrintSettings (1:1)
- NoiseAssessment has many: NoiseAssessmentResult (loose FK), MitigationMeasure, AssessmentDocument, AISuggestion, AIInteraction
- No junction table between assessment and noise sources — data flows via PhaseExposure (runtime dataclass, NOT persisted)

## DOCX Generation (6 sections)
1. identificazione — company data
2. processi — activities/processes
3. valutazione — risk evaluation results
4. misure_prevenzione — prevention measures
5. sorveglianza — health surveillance
6. formazione — training

## Credentials
- Admin: admin@mars-dev.com / MarsAdmin2026!
- Tenant slug: mars-admin-3
- Test company: ACME S.r.l. (ateco 25.11.00)

## Frontend Files (current)
- static/index.html — SPA layout, Google Fonts (Fraunces + DM Sans)
- static/css/main.css — industrial HSE design (navy+amber), 1100+ lines
- static/js/auth.js — AuthService with JWT refresh
- static/js/api-client.js — full API client (70 endpoints)
- static/js/app.js — SPA with 6-tab assessment detail, AI panel, calculations

## Migrations (11 applied: 001-011)
- 010: `_is_deleted` on Company + FK `company_id` constraints
- 011: 12 performance indexes

## DIVISION_TO_MACRO_CATEGORY map
Includes "99" → "U". Unknown division: use "04" for tests.

## CORS
`allow_headers` uses `settings.cors_headers` (Content-Type, Authorization, X-Request-ID)

## Audit Middleware
Uses `get_session_factory()` with `async with` + `finally: close()`

## Accomplished Waves
Wave 6-15: CRUD APIs, security hardening, CI/CD, frontend redesign, cleanup
Wave 16-23: Full frontend (all 70 endpoints wired, 6-tab detail, AI agents, calculations, catalog, companies, settings with license)

## Test Count: 239 passed (all green)