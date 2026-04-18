# Implementation Status — MARS DVR Rumore

> Dashboard di stato per ripristino lavoro da altre sessioni/macchine/agenti.
> Ogni wave aggiorna questo file al completamento.

**Last updated**: 2026-04-18 (Wave 27 AI Autopilot core end-to-end + Wave 29 + W26 foundation + W25-lite — 4 PR stack su GitHub)
**Current branch Rumore**: `wave-27-ai-autopilot` (branched from wave-25-lite-context, 5 commit + 60 test)
**Current branch MARS**: `noise-module-integration` (M4 committed, cabcf1f — locale, non pushato)
**DB strategy**: Docker ELIMINATO. SQLite via conftest TypeDecorator swap; PG default in prod. **375 test PASS.**
**Flow E2E funzionante**: frontend iframe → MARS JWT → /contexts/bootstrap → /autopilot/run (SSE) → /suggestions/* (approve/reject/bulk). Mock LLM di default; prod swap via DI.
**Next action**: (1) Push `wave-27-ai-autopilot` e apri PR, (2) Wire OllamaProvider in prod via dependency_overrides o settings-based factory, (3) Wave 30 Hardening (logging, healthcheck, Prometheus), (4) coordina Wave 24 MARS per l'altra sessione

---

## Planning phase ✅ DONE

- [x] Spec: `docs/superpowers/specs/2026-04-17-mars-dvr-rumore-completion-design.md`
- [x] Index: `docs/superpowers/plans/2026-04-17-00-index.md`
- [x] Wave 24 plan: MARS modifications (11 task)
- [x] Wave 25 plan: DB refactoring (11 task)
- [x] Wave 26 plan: MARS integration backend (9 task)
- [x] Wave 27 plan: AI Autopilot (7 task)
- [x] Wave 28 plan: Scheduler (8 task)
- [x] Wave 29 plan: Frontend (8 task)
- [x] Wave 30 plan: Hardening (7 task)
- [x] Wave 31 plan: E2E testing (4 task)
- [x] Custom agent `.claude/agents/mars-backend-dev.md`
- [x] Memory persistence in `C:\Users\Salvatore Romano\.claude\projects\.../memory/`

---

## Execution phase 🚧 PARTIALLY STARTED

| Wave | Plan file | Status | Branch | Notes |
|---|---|---|---|---|
| W24 | `2026-04-17-wave-24-mars-modifications.md` | 🚧 in-progress | `noise-module-integration` (MARS repo) | M4 done (cabcf1f); M1/M5/M6 bloccati per discrepanza plan vs struttura MARS reale. Deprioritizzato (altra sessione Claude) |
| W25 | `2026-04-17-wave-25-db-refactoring.md` | 🔻 descoped → W25-lite | `wave-25-db-refactoring` (empty, deprecato) | Full UUID+outbox refactor deprioritizzato. Scope ridotto a W25-lite: solo NoiseAssessmentContext model/migration/service/routes (4 commit, 21 test). PR #5. |
| W26 | `2026-04-17-wave-26-mars-integration.md` | 🚧 foundation done | `wave-26-mars-foundation` | Task 1-4 done (MarsApiClient, JwtValidator, TenantResolver, FastAPI dep). Task 5-8 richiedono modelli Wave 25. 55 unit test PASS. |
| W27 | `2026-04-17-wave-27-ai-autopilot.md` | ✅ core done | `wave-27-ai-autopilot` | ExposureEstimatorAgent + SuggestionServiceV2 + /suggestions + Orchestrator + /autopilot SSE. Stubs per review/mitigation/narrative agents (future). 60 new test PASS. PR #6 |
| W28 | `2026-04-17-wave-28-scheduler.md` | ⏳ not started | — | Code-only is writable ora; tests richiedono DB |
| **W29** | `2026-04-17-wave-29-frontend.md` | **✅ DONE** | `wave-29-frontend` | 8 commit, 0 Docker dependency, frontend P0 completo |
| W30 | `2026-04-17-wave-30-hardening.md` | ⏳ not started | — | Depends on W26-W28 |
| W31 | `2026-04-17-wave-31-e2e.md` | ⏳ not started | — | Depends on all |

### Wave 29 Progress Detail

| Task | Status | Commit SHA | Notes |
|---|---|---|---|
| Task 1 ModuleBootstrap | ✅ done | `d5a83d0` | postMessage handshake, 3 modi (mars-iframe, standalone-dev, standalone-login) |
| Task 2 APIClient extension | ✅ done | `a75696c` | +10 metodi (bootstrapContext, runAutopilot SSE, suggestions v2, audit) + iframe-mode 401 fix in auth.js |
| Task 3 AutopilotView | ✅ done | `0654ca3` | SSE progress streaming + result dashboard risk-banded + error/retry |
| Task 4 SuggestionCard+View | ✅ done | `8103578` | Per-type rendering, bulk toolbar, edit modal con form strutturato per phase_laeq/mitigation |
| Task 5 SafeEditor | ✅ done | `77fcd2b` | UndoStack debounced + DOMPurify paste sanitize + keyboard shortcuts |
| Task 6 AuditTrailPanel | ✅ done (frontend) | `e45397b` | Frontend completo; backend endpoint 404 graceful (dipende W25 AuditLog + W26 MarsContext) |
| Task 7 Design tokens | ✅ done | `eb4a5d2` | Brand+semantic+risk-band (Art. 188) + typography + spacing/radius/shadow scales |
| Task 8 Smoke test + STATUS | 🚧 in progress | — | Sintassi JS verificata, file inventory coerente |

### Wave 24 Progress Detail

| Task | Status | Commit SHA | Notes |
|---|---|---|---|
| Task 1 Setup branch | ✅ done | — | Branch `noise-module-integration` creato |
| Task 5 M4 DVR contract v1.1 | ✅ done | `cabcf1f` | Zod + JSON schema + KNOWN_RISK_MODULES |
| Task 2 M5 JWT tenant_id | ⚠️ plan revise | — | Plan presume passport-jwt Strategy; MARS usa `userFromAccessToken()` pattern |
| Task 3 M1 GET /me | ⚠️ plan revise | — | Endpoint esiste già; va arricchito con tenantId+enabledModules |
| Task 4 M6 verify module | ⚠️ plan revise | — | Struttura `src/` flat, non `src/client-app/` |
| Task 6 M3 module-extensions PUT | ⚠️ plan revise | — | `src/dvr-documents.controller.ts` esiste flat |
| Task 7 M2 register-session | ⚠️ plan revise | — | Nuovo controller da creare (flat) |
| Task 8 M7 webhook events | ⚠️ plan revise | — | Adattare a struttura flat |
| Task 9 M8 ModuleFrame | ✅ plan OK | — | apps/web/ path OK in plan |
| Task 10 M9 ATECO 2025 seed | ✅ plan OK | — | script standalone, nessuna dipendenza struttura |

---

## Blockers / open questions

1. **🚨 Docker Desktop non running** — blocca Wave 25 (Postgres per test migrations)
2. **🚨 Plan Wave 24 vs realtà MARS** — struttura flat `src/*.ts` (non `src/auth/...`). Auth pattern via `userFromAccessToken()`, no JwtAuthGuard. `me()` esiste già. Plan va revisionato prima di committare M1/M5/M6.
3. **MARS staging URL**: servirà per E2E test finale in W31
4. **Ollama Cloud rate limit**: budget AI call durante W27 golden dataset
5. **PAF scraping delta**: valutare se fare prima sync iniziale per test W28
6. **Secrets rotation**: post-execution prima di push in production (secrets visti da agente AI)

---

## Quick commands

```bash
# Avvia sviluppo
cd "C:/Users/Salvatore Romano/Desktop/MARS_DVR_Rumore"
make dev        # FastAPI :8085
make test       # fast tests

# Start scheduler (dopo Wave 28)
python -m src.infrastructure.scheduler.runner

# Clone MARS repo (per Wave 24)
cd "C:/Users/Salvatore Romano/Desktop"
git clone https://github.com/SkaRomance/MARS.git MARS_inspect

# Spawn mars-backend-dev agent
# (nel prompt Claude Code: "Delega W24 all'agente mars-backend-dev")
```

---

## Log esecuzione (aggiornare durante lavoro)

### 2026-04-17 — planning day
- 10:00 UTC — audit codebase completo (4 agenti paralleli)
- 11:30 UTC — brainstorming skill, domande chiarificatrici
- 13:00 UTC — design doc scritto e approvato
- 14:30 UTC — custom agent `mars-backend-dev` creato
- 15:00 UTC — tutti gli 8 plan wave scritti e committati
- 16:00 UTC — STATUS.md creato; execution può iniziare

### Esecuzione 🚧

**2026-04-17 — session chiusura / 2026-04-18 early work**
- Push plan su branch `planning/mars-dvr-rumore-design-and-plans` → PR #2 aperta
- Smoke check environment: Docker ❌, MARS_inspect ✅, venv ⚠️
- Branch `wave-25-db-refactoring` creato (vuoto, bloccato su Docker)
- Subagent `mars-backend-dev` spawned su Wave 24 → crash API JSON a 49s; M4 completato e committato (cabcf1f)
- Scoperta discrepanza plan Wave 24 vs struttura reale MARS flat
- STATUS.md aggiornato con dettagli e prossimi passi

**2026-04-18 — Wave 27 AI Autopilot execution**
- Branch `wave-27-ai-autopilot` da `wave-25-lite-context`
- 5 commit atomici:
  - `e0ac8e7` ExposureEstimatorAgent + prompt ITA (Art. 188 framework, K corrections ISO 9612) + types — 13 test
  - `58437f3` SuggestionServiceV2 + migration 013 (context_id FK su ai_suggestion, assessment_id nullable) + model adapter — 14 test
  - `5f6cf53` /suggestions/* routes V2 (by-context, approve, reject, bulk con min_confidence) — 13 test
  - `1d3b52d` AutopilotOrchestrator (async generator SSE events, ISO 9612 LEX,8h calc, risk banding) — 10 test
  - `c7d691b` /autopilot/* SSE routes (run streaming, status, cancel, cross-tenant 404, missing snapshot 409) — 10 test
- Net sessione: 60 nuovi test backend, 375 totali PASS (+60 vs W25-lite)
- Pattern: MockProvider di default per il LLM → tests deterministici senza API key
- Stubs intenzionali: review/mitigation/narrative agents emettono step_completed con "pending future wave" — UI Wave 29 progress bar accurata, future agent plug-in senza toccare SSE

**2026-04-18 — W25-lite context service execution**
- Pivot su "no Docker" per l'utente: scoperto che tests esistenti già giravano su SQLite via conftest TypeDecorator swap → 294 test PASS senza Docker
- Descoping W25 full DB refactoring (UUID migration + outbox + audit v2) → **W25-lite** focalizzato solo su NoiseAssessmentContext (il blocker funzionale per il frontend)
- Branch `wave-25-lite-context` da `wave-26-mars-foundation`
- 4 commit con test:
  - `fe7e4f6` NoiseAssessmentContext model + enum (registrato in models/__init__)
  - `c30d40c` Alembic migration 012 (UNIQUE tenant+doc+rev, composite tenant+updated_at index)
  - `81d6b87` NoiseAssessmentContextService (11 integration test SQLite: bootstrap create/fresh/stale/force/no-revision, get_by_dvr/id tenant isolation, list status filter, update_status, unique constraint idempotence)
  - `7c671d8` /contexts routes + schemas (10 api test: bootstrap, idempotence, no-auth 401, get by id, cross-tenant 404, by-dvr, list, update status, 422 invalid, by-dvr missing 404)
- Fix bug scoperto: `/contexts` (no slash) collide con `assessments/{assessment_id}` route match. Aggiunto trailing `/` esplicito. Conflitto scoperto in test routing, fixato in 1 commit.
- Fix bug SQLAlchemy: `update_status` ora fa `session.refresh(ctx)` dopo flush per evitare MissingGreenlet sul lazy-load di `updated_at` (server_default=func.now()) durante serializzazione Pydantic post-commit.
- Net totale sessione: 76 nuovi backend test (55 Wave 26 foundation + 21 W25-lite), 315 test PASS

**2026-04-18 — Wave 26 MARS foundation execution**
- Branch `wave-26-mars-foundation` creato da `wave-29-frontend` (layer ortogonale: frontend JS vs backend Python)
- Scoping: solo Task 1-4 DB-independent (Task 5+ richiedono NoiseAssessmentContext da Wave 25)
- Config: +12 settings `mars_*` in `src/bootstrap/config.py` (dual-algorithm RS256/HS256, JWKS + tenant cache TTLs, retry/timeout)
- 4 commit atomici con test:
  - `d0ba41c` MarsApiClient + exceptions + types (16 test)
  - `51d87ce` MarsJwtValidator + JWKS cache (17 test)
  - `a27a91d` TenantResolver + Redis duck-type cache (10 test)
  - `f867d0a` require_mars_context + require_module_access (12 test)
- Tooling scelto: `httpx.MockTransport` invece di respx, fake in-memory cache invece di fakeredis → zero nuove dep
- Test suite: 137 unit test PASS, 0 fail, 0 regression su auth/domain/rag esistenti
- Gap: Task 5 (DvrSnapshotService), Task 6 (route refactor), Task 7 (migration 016), Task 8 (Outbox) bloccati finché Wave 25 DB models esistono

**2026-04-18 — Wave 29 Frontend execution**
- User pivot: deprioritizza Wave 24 MARS (altra sessione in parallelo), focus su funzionalità modulo Rumore
- Creato branch `wave-29-frontend` da master
- Adattata strategia plan: NON rimpiazzare `api-client.js` (rompe 70 endpoint wired in app.js 94KB); invece estensione additiva
- 8 commit atomici per task (d5a83d0 → eb4a5d2):
  - ModuleBootstrap + iframe-mode 401 fix in auth.js (non-breaking)
  - APIClient +10 metodi (bootstrapContext, runAutopilot SSE, suggestions v2, audit)
  - AutopilotView (SSE streaming, progress, result risk-banded, error/retry)
  - SuggestionCard+View (bulk, edit modal strutturato phase_laeq/mitigation)
  - SafeEditor+UndoStack (debounce 300ms, DOMPurify paste, keyboard)
  - AuditTrailPanel (frontend; backend endpoint graceful 404 fino Wave 25+26)
  - Design tokens (brand, risk-band Art. 188, typography, scales 4px-based)
- Syntax check nodejs: PASS tutti 7 file JS nuovi
- File inventory: 9 JS + 5 CSS + index.html refs tutti coerenti
- Gap noto: AuditTrailPanel mostra "Registro non ancora disponibile" fino a quando backend audit è live (post Wave 25+26)
- Branch pronto per push + PR
