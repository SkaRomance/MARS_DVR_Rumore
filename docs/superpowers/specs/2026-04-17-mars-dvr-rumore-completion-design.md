# Design — MARS DVR Rumore completion & MARS integration

**Autore**: Salvatore Romano + Claude Opus 4.7
**Data**: 2026-04-17
**Status**: Draft (pending user review)
**Milestone target**: End-to-end MVP funzionante + integrazione MARS

---

## 1. Contesto e obiettivi

Il modulo **MARS DVR Rumore** è un sistema specialistico per la valutazione del rischio rumore ex D.Lgs. 81/2008 (Titolo VIII Capo II), costruito come plugin della piattaforma **MARS** (software consulenti HSE italiano, monorepo NestJS + React, repo `SkaRomance/MARS`).

Il backend (FastAPI + SQLAlchemy async + Ollama + ChromaDB + Keygen) è avanzato (~70 endpoint, 11 migration, 6 agenti AI, RAG, DOCX export). Il frontend (Vanilla JS SPA) è ~60% completo. Mancano MARS integration contract, AI Autopilot centrale, completamento UX P0, scheduler scraping, hardening.

**Obiettivi di questa iterazione**:

1. **MARS integration**: trasformare il modulo da standalone a "thin plugin" del DVR Generale (MARS = single source of truth).
2. **AI Autopilot**: far diventare l'AI il perno del prodotto — valutazione autonoma della prima bozza, consulente affina.
3. **Frontend completion**: AI approve/reject workflow, editor safety, audit UI, iframe embedding.
4. **Scraping + sync normativo**: scheduler APScheduler per PAF, ATECO 2025, Gazzetta Ufficiale watchdog, RAG re-index.
5. **Hardening + cloud-native readiness**: structlog JSON, healthcheck completo, outbox pattern, UUID migration, non-root container, CI deploy stage.

**Non obiettivi**:

- Migrazione frontend Rumore da Vanilla JS a React (rimandata a Phase 6 post-MVP).
- Build del cloud nativo MARS (non esiste ancora; lasciamo architettura aperta).
- Partnership/negoziazione licensing PAF (decisione di prodotto, fuori scope tecnico).
- Implementazione degli altri moduli rischio (Vibrazioni, Chimico ecc.).

---

## 2. Architettura target

### 2.1 Topologia

```
┌──────────────────────────────────────────────────────────────────┐
│ Consulente HSE browser                                            │
│                                                                    │
│  ┌──────────────────────────────────────┐                         │
│  │ MARS web (Vite React 19) apps/web    │                         │
│  │  ├─ DVR Generale editor              │                         │
│  │  └─ ModuleFrame "Rumore" iframe  ◄───┼─────┐                   │
│  └──────────────────────────────────────┘     │                   │
└────────────────────────────────────────────────┼──────────────────┘
                                                  │ postMessage + JWT handshake
                                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│ Rumore FastAPI + static/ (Vanilla JS SPA)                          │
│  - Valida JWT MARS (JWKS o shared secret)                          │
│  - Risolve tenantId via GET /me su MARS                            │
│  - UI: autopilot, fasi, calcolo LEX, editor sezioni, audit         │
│                                                                    │
│  DB Rumore (Postgres): dati noise-specifici (no company/user dup)  │
└─────┬─────────────────────────────────────────────────────────────┘
      │ REST (Bearer JWT) + webhook inbound (eventi DVR update)
      ▼
┌───────────────────────────────────────────────────────────────────┐
│ MARS api (NestJS 10) apps/api                                     │
│  - /me (nuovo)                                                    │
│  - /client-app/compliance/modules/verify/:key (nuovo)             │
│  - /dvr-documents/:d/revisions/:r/module-extensions/:key (nuovo)  │
│  - DVR contract v1.1 (nuovo field module_extensions)              │
│  - Webhook outbound /events (nuovo)                               │
│  DB MARS (Postgres): single source of truth                       │
│  S3 MinIO: attachments                                            │
└───────────────────────────────────────────────────────────────────┘

Rumore Scheduler (container separato APScheduler):
  - cron weekly PAF delta sync
  - cron weekly ATECO check
  - cron 6h Gazzetta Ufficiale + EUR-Lex watchdog
  - cron daily RAG re-index
  - cron 5min outbox dispatcher (log-only finché cloud nativo esiste)
```

### 2.2 Principi architetturali

1. **Thin plugin**: MARS = single source of truth. Rumore non duplica Company/UnitSite/User/Tenant.
2. **AI-first UX**: autopilot produce valutazione autonoma; consulente affina.
3. **Cloud-native ready**: UUID globali, outbox pattern, audit log completo, soft delete universale, API versioning — pronti per futura migrazione cloud MARS senza refactor.
4. **Compliance by design**: ogni dato ha `origin` (measured/declared/estimated/ai_suggested/validated), audit trail tracciabile per D.Lgs. 81/2008.
5. **Backward compat**: modifiche MARS additive, schema DVR versioned, nessun breaking change.

---

## 3. Data model

### 3.1 Rumore DB — entità finali (post-refactoring)

Rimuoviamo duplicazioni di MARS e teniamo solo dati noise-specifici.

**Drop** (duplicate MARS, rimozione via migration 016 dopo data migration pulita): `company`, `tenant`, `user` (Rumore-side), `audit_log` legacy. La relazione ora è solo logica verso MARS tramite `mars_*_id: UUID` (no FK fisica cross-DB).

**Nuove/rinominate**:

```
NoiseAssessmentContext
  id: UUID PK
  mars_dvr_document_id: UUID (FK logica MARS)
  mars_revision_id: UUID
  mars_tenant_id: UUID
  mars_company_id: UUID
  ateco_code: string
  status: enum(ai_drafting|draft|review|published|archived)
  ai_autopilot_status: enum(pending|running|completed|failed)
  ai_autopilot_completed_at: timestamptz
  ai_overall_confidence: float
  locked_by: UUID, locked_at: timestamptz
  created_at, updated_at, deleted_at

NoiseExposurePhase (ex NoiseAssessmentPhase)
  id: UUID, context_id: UUID FK
  mars_work_phase_id: UUID, mars_work_phase_name: string (snapshot)
  laeq_db: float, laeq_origin: enum, laeq_uncertainty_db: float
  duration_hours: float, duration_origin: enum
  lcpeak_db: float nullable
  k_impulse, k_tone, k_background: float default 0
  ai_suggestion_id: UUID nullable
  approved_by, approved_at
  created_at, updated_at, deleted_at

NoiseCalculationResult
  id: UUID, context_id: UUID FK
  lex_8h_db, lex_weekly_db, uncertainty_combined_db, uncertainty_extended_db
  risk_band: enum(green|yellow|orange|red)
  confidence_score: float
  calculation_inputs_json: jsonb
  calculated_at

NoiseSourceCatalog (PAF data, read-only)
  id: UUID, paf_obj_id: string UNIQUE
  brand, model, type, power_source
  laeq_min, laeq_typ, laeq_max: float, lcpeak_db nullable
  source_protocol: string, last_synced_at
  raw_text, raw_html

AIInteraction
  id: UUID, context_id: UUID FK nullable
  agent_type: enum(bootstrap|source_detection|exposure_estimator|review|
                   mitigation|narrative|explain|autopilot)
  prompt_hash, prompt_full: text
  response_json: jsonb
  llm_model, tokens_prompt, tokens_completion, latency_ms
  rag_chunks_used: jsonb
  confidence: float nullable
  created_at

AISuggestion
  id: UUID, interaction_id FK, context_id FK
  suggestion_type: enum(phase_laeq|phase_duration|mitigation|training|
                        narrative_section|k_correction)
  target_entity_type, target_entity_id
  payload_json: jsonb
  confidence: float
  status: enum(pending|approved|rejected|superseded)
  approved_by, approved_at, rejected_by, rejected_at, rejection_reason
  created_at

AssessmentDocument
  id: UUID, context_id FK
  version: int, format: enum(docx|pdf|json), s3_key
  language: enum(it|en), generated_by: enum(ai|user|hybrid)
  file_size_bytes, created_at

RumoreOutbox (cloud-native readiness)
  id: UUID, aggregate_id: UUID
  event_type: string (noise.*)
  payload_json: jsonb
  created_at
  dispatched_at: timestamptz nullable
  dispatcher: string nullable

AuditLog (unified compliance trace)
  id: UUID, tenant_id: UUID, user_id: UUID nullable
  source: enum(user|ai_autopilot|ai_agent|system|scheduler)
  entity_type, entity_id
  action: enum(create|update|delete|approve|reject|calculate|export|ai_run)
  before_json, after_json: jsonb
  created_at
```

### 3.2 MARS DB — minori aggiunte

- JWT claim opzionale `tenant_id` nei token (backward compat: parser accetta assenza).
- Nessuna nuova tabella necessaria; DVR JSON snapshot supporta `module_extensions` nativamente con schema v1.1.

### 3.3 DVR Contract v1.1 — snippet

```json
{
  "schemaVersion": "1.1.0",
  "module_extensions": {
    "noise": {
      "module_version": "0.1.0",
      "assessment_context_id": "uuid",
      "lex_8h_summary": { "value": 85.2, "risk_band": "ORANGE" },
      "phases": [ /* snapshot per export convenience */ ],
      "last_sync_at": "ISO"
    }
  }
}
```

Backward compat: v1.0 parser ignora il campo. v1.1 parser accetta assenza.

---

## 4. Modifiche MARS (SkaRomance/MARS)

Delegate all'agente `mars-backend-dev`. Lavorano su branch `noise-module-integration`.

| ID | Modifica | File | Effort |
|---|---|---|---|
| M1 | `GET /me` → {userId, email, tenantId, enabledModules, rolesByCompany} | `apps/api/src/auth/auth.controller.ts` | 1h |
| M2 | `POST /modules/:key/register-session` — il modulo notifica MARS di iniziare lavoro su una revision; MARS ritorna `session_id` + `revision.updatedAt` per optimistic lock. Nessun lock hard, solo marker per conflict detection | `apps/api/src/modules/modules.controller.ts` (nuovo) | 2h |
| M3 | `PUT /dvr-documents/:d/revisions/:r/module-extensions/:key` con optimistic lock | DVR controller | 2h |
| M4 | Schema `dvr.descriptor.v1.1.json` + Zod type in `packages/contracts` | package contracts | 1h |
| M5 | JWT claim `tenant_id` opzionale in `issueTokens` | auth.service.ts | 30min |
| M6 | `POST /client-app/compliance/modules/verify/:key` (200/402/403) | client-app controller | 1h |
| M7 | Webhook outbound DVR events (env `MODULE_EVENTS_WEBHOOK_URL`, HMAC signed) | events.service.ts (nuovo) | 3h |
| M8 | `ModuleFrame.tsx` in apps/web con postMessage handshake | apps/web/src/components/modules/ | 2-3h |
| M9 | ATECO 2025 PDF → JSON canonico → Prisma seed | prisma/seeds/ateco_2025.ts | 2h |

**Totale**: ~14-16h. Parallelizzato con modulo Rumore.

---

## 5. AI Autopilot — flagship feature

### 5.1 Pipeline 9-step

```
1. Parse DVR snapshot (company, workPhases, phaseEquipments)
2. SourceDetectionAgent (parallel per equipment) → match PAF
3. ExposureEstimatorAgent (parallel per workPhase) → durata + LAeq
4. Deterministic calc ISO 9612 → LEX_8h, uncertainty, risk_band
5. ReviewAgent → validation coerenza + flag outlier
6. MitigationAgent (if risk ≥ yellow) → misure tecniche/organizzative/DPI
7. NarrativeAgent → sezioni DVR in italiano giuridico
8. Persist → NoiseExposurePhase, NoiseCalculationResult, AISuggestion*, AIInteraction, Outbox event
9. Notify UI via SSE → autopilot_status=completed
```

### 5.2 UX landing autopilot

- Progress bar streaming con step list + percentage
- On completion: dashboard pre-compilata con LEX medio, band, fasi critiche, suggerimenti
- Consulente: "Rivedi", "Approva tutto", "Modifica", "Modalità manuale"

### 5.3 Approve/reject granulare

Per ogni `AISuggestion`:
- Approve (standard)
- Approve & Edit (apre modal, marca `origin=user_validated_ai`)
- Reject (con motivazione opzionale, resta in audit)
- Request re-run (prompt extra dal consulente)

Bulk: "Approva confidence > 0.8", "Rigetta < 0.5", "Escludi fase X".

### 5.4 Audit trail AI vs user

Ogni campo ha `origin` enum. Export audit CSV per compliance. Disclaimer obbligatorio nel DVR finale.

### 5.5 Agent nuovi

- `ExposureEstimatorAgent` — durata esposizione da fase+mansione+equipment.
- `AutopilotOrchestratorAgent` — coordina pipeline async.

Prompt templates versioned in `src/domain/services/prompts/templates/`.

---

## 6. Frontend completion

### 6.1 Strategia

Mantenere Vanilla JS. Iframe embedding in MARS web. React migration = Phase 6.

### 6.2 Componenti P0

| Componente | File | Scopo |
|---|---|---|
| `AutopilotView` | `static/js/views/autopilot.js` | Landing + progress SSE + result dashboard |
| `SuggestionCard` | `static/js/components/suggestion.js` | Approve/Edit/Reject/Re-run + bulk toolbar |
| `SafeEditor` | `static/js/components/safe-editor.js` | Undo/redo (50 steps) + paste sanitize via API |
| `AuditTrailPanel` | `static/js/components/audit-trail.js` | Lista modifiche con filtri + export CSV |
| `ModuleBootstrap` | `static/js/module-bootstrap.js` | Handshake iframe: postMessage JWT + DVR context |
| `ApiClientV2` | `static/js/api-client.js` (refactor) | Timeout 30s, retry esponenziale, centralized errors |
| `AppShell` | `static/js/app.js` (refactor) | View lifecycle onMount/onUnmount per no memory leak |

### 6.3 Design tokens condivisi

`static/css/design-tokens.css` con CSS vars matching MARS (colors, spacing, typography). Source of truth: MARS.

---

## 7. Scheduler + Sync normativo

### 7.1 APScheduler in processo separato (container `scheduler`)

```python
scheduler = AsyncIOScheduler()
scheduler.add_job(paf_delta_sync, CronTrigger(day_of_week='sun', hour=3))
scheduler.add_job(ateco_sync_check, CronTrigger(day_of_week='mon', hour=4))
scheduler.add_job(normativa_watchdog, CronTrigger(hour='*/6'))
scheduler.add_job(rag_reindex_if_stale, CronTrigger(hour=5))
scheduler.add_job(outbox_dispatch, IntervalTrigger(minutes=5))
```

### 7.2 Watchdog normativo — 3 fonti

1. **Gazzetta Ufficiale** RSS (filter keywords D.Lgs. 81, rumore, sicurezza)
2. **EUR-Lex** search (noise directive 2003/10/CE)
3. **INAIL Open Data** API

Match → crea `NormativaUpdate` record → flag RAG re-index → webhook MARS admin.

### 7.3 RAG re-index

Detect nuovi PDF in `paf_library/` + `data/normativa/` via hash → batch re-embed in ChromaDB.

---

## 8. Hardening Phase 5 + Cloud-native readiness

### 8.1 Observability

- **structlog JSON** con request_id, tenant_id, user_id, correlation_id
- **Healthcheck completo** `GET /health` parallel: DB + Redis + Ollama + MARS API + ChromaDB
- **Prometheus metrics** via `prometheus-fastapi-instrumentator`

### 8.2 Cloud-native fondamenta

- **UUID migration** (Alembic 012): int id → UUID per entità Rumore-specifiche
- **Outbox** (013): tabella + dispatcher log-only
- **AuditLog unified** (014)
- **Soft delete universale** (017)
- **API versioning** `/api/v1/noise/` confermato

### 8.3 Security

- Secrets rotation runbook `docs/operations/secrets-rotation.md`
- Container non-root (`USER appuser` in Dockerfile)
- Docker resource limits in compose
- Nginx rate limit aggiuntivo

### 8.4 CI/CD deploy

`.github/workflows/deploy.yml`:
- Build + Trivy scan
- Push GHCR
- Manual trigger staging/prod
- Health check post-deploy + rollback

---

## 9. Testing strategy

| Layer | Tool | Scope |
|---|---|---|
| Unit | pytest | ISO 9612, chunker, prompt parsers, outbox |
| Integration | pytest + testcontainers | DB, MARS API mock (wiremock), Ollama mock |
| E2E backend | pytest + httpx | import DVR → autopilot → export DOCX |
| E2E browser | Playwright MCP | AutopilotView, suggestion approval, editor, iframe |
| AI golden | pytest | 20 esempi canonici per agent con tolerance |
| Load | locust | 50 concurrent autopilot sessions |

Golden dataset critico per regression testing AI.

---

## 10. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| AI hallucination su valutazione | HIGH — compliance | Confidence threshold, disclaimer, audit trail, Review agent validator, approve/reject obbligatorio |
| MARS API outage durante autopilot | MED | Retry esponenziale, degraded mode offline, re-sync on recovery |
| Ollama cloud rate limit/downtime | MED | Fallback Ollama locale, queue priority |
| PAF licensing claim | HIGH | Disclaimer esplicito, kill-switch, roadmap banca dati propria |
| Concurrency edit DVR | MED | Optimistic lock via revision.updatedAt, auto-merge field-level |
| Breaking change DVR schema | LOW | Versioned schema, backward-compat validator |
| Cloud nativo futuro refactor | LOW | Outbox + UUID + audit già pronti |
| HTML injection editor | MED | nh3 server + DOMPurify client |

---

## 11. Implementation plan overview

8 wave atomiche, ~16-20h totali. Handoff dettagliato a `writing-plans` skill.

**Parallelizzazione**: Wave 24 (MARS modifications) delegata all'agente custom `mars-backend-dev` creato in `.claude/agents/mars-backend-dev.md`. Lavora su repo MARS clonato in `C:/Users/Salvatore Romano/Desktop/MARS_inspect/` su branch `noise-module-integration`. Può procedere in parallelo con Wave 25-28 su modulo Rumore.

**Checkpoint obbligatori** tra wave:
- Dopo W25 (DB refactor): test suite passing + rollback verificato
- Dopo W26 (MARS integration): mock MARS API funzionante + JWT validation OK
- Dopo W27 (Autopilot): golden dataset tests tutti verdi
- Dopo W29 (Frontend): Playwright smoke test passing
- Dopo W30 (Hardening): health check 5/5 verde

**Strategia commit**: 1 commit atomico per ogni sub-task (W24.1, W24.2, ...) con test passing. No bulk commits. Se un test fallisce, revert + retry.


```
WAVE 24 — MARS repo preparation (sub-agent mars-backend-dev)
  W24.1-10 M1..M9 implementations + tests + PR

WAVE 25 — Rumore DB refactoring (cloud-native foundations)
  W25.1-8 Alembic migrations 012-018

WAVE 26 — MARS integration backend
  W26.1-6 MarsApiClient, JWT validation, tenantId resolver,
          middleware, DvrSnapshotService, integration tests

WAVE 27 — AI Autopilot orchestrator
  W27.1-6 ExposureEstimatorAgent, AutopilotOrchestrator pipeline,
          SSE endpoint, approve/reject endpoints, audit log, golden tests

WAVE 28 — Scheduler + Sync normativo
  W28.1-6 APScheduler setup, PAF/ATECO/Normativa/RAG/Outbox jobs

WAVE 29 — Frontend P0 completion
  W29.1-6 ModuleBootstrap, AutopilotView, SuggestionCard,
          SafeEditor, AuditTrailPanel, design tokens

WAVE 30 — Hardening
  W30.1-6 structlog, health, Prometheus, non-root,
          CI deploy, operations docs

WAVE 31 — E2E testing + closure
  W31.1-4 Playwright autopilot, suggestion, load test, staging
```

---

## 12. Success criteria

MVP è done quando:

1. Consulente apre modulo Rumore da iframe MARS web, vede DVR workPhases importati automaticamente
2. AI Autopilot parte automaticamente, produce valutazione in < 90s per DVR medio
3. Consulente può approve/reject ogni suggestion (individual + bulk)
4. Editor sezioni DVR ha undo/redo + paste safe
5. AuditTrailPanel mostra ogni modifica AI vs user con export CSV
6. PUT sul DVR MARS aggiorna `module_extensions.noise` con snapshot valutazione
7. Export DOCX include sezione Rumore con disclaimer compliance AI
8. Scheduler esegue almeno un ciclo PAF delta + normativa watchdog senza errori
9. Healthcheck riporta 5/5 servizi healthy
10. Tutti i test (unit + integration + E2E Playwright) passano in CI
11. MARS ha endpoint `/me`, `/modules/.../verify`, contract v1.1, ModuleFrame
12. ATECO 2025 seedato in MARS, mapping disponibile per modulo Rumore

---

## 13. Open questions (per ulteriore approfondimento)

1. **AI provider fallback**: se Ollama Cloud è giù, accettiamo degraded mode (calc deterministico + alert) oppure fallback automatico a OpenAI/Gemini (richiede API keys)?
2. **Concorrency revision DVR**: se 2 moduli (Rumore + Vibrazioni) scrivono contemporaneamente, last-write-wins o merge campo-level? Raccomando campo-level per robustezza.
3. **Webhook auth MARS → Rumore**: HMAC-SHA256 con secret condiviso. Quale policy di rotation?
4. **Iframe domain policy**: Rumore deve essere su subdomain MARS (noise.mars.example.com) o cross-origin? CSP headers da definire.
5. **PAF data retention**: quando PAF viene rimosso (es. deprecato), i NoiseExposurePhase storici devono mantenere il riferimento? Sì (soft delete).

---

## 14. Riferimenti

- `CONTEXT_FOR_CODING_AGENT.md` — product identity & scope
- `PLANNING.md` — architettura originale
- `STRUCTURED_PLAN_PHASE1.md`, `PHASE2.md`, `PHASE3.md`
- `PAF_EXPORT_STRATEGY.md`
- `DEVOPS_DEPLOYMENT_ANALYSIS.md`
- `TESTING_STRATEGY.md`
- Repo MARS: `https://github.com/SkaRomance/MARS`
- `packages/contracts/schemas/dvr.descriptor.v1.json` (MARS)
- `docs/dvr-contract.md` (MARS)

Memoria Claude con decisioni live:
- `memory/project_mars_contract.md`
- `memory/project_ai_centrality.md`
- `memory/project_tech_stack.md`
