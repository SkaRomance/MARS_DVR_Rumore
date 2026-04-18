# Implementation Status — MARS DVR Rumore

> Dashboard di stato per ripristino lavoro da altre sessioni/macchine/agenti.
> Ogni wave aggiorna questo file al completamento.

**Last updated**: 2026-04-18 (Wave 24 partially started, Wave 25 blocked on Docker)
**Current branch Rumore**: `master` (planning branch pushed as PR #2); `wave-25-db-refactoring` branch created empty
**Current branch MARS**: `noise-module-integration` (M4 committed, cabcf1f)
**Next action**: (1) Avvia Docker Desktop, (2) revisiona Wave 24 plan per adattare struttura flat MARS, (3) completa M1/M5/M6 su MARS, (4) parti con Wave 25 su Rumore

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
| W24 | `2026-04-17-wave-24-mars-modifications.md` | 🚧 in-progress | `noise-module-integration` (MARS repo) | M4 done (cabcf1f); M1/M5/M6 bloccati per discrepanza plan vs struttura MARS reale |
| W25 | `2026-04-17-wave-25-db-refactoring.md` | ⏸ blocked | `wave-25-db-refactoring` (empty) | Blocked: Docker Desktop non running |
| W26-W31 | vari | ⏳ not started | — | Depends on W24+W25 |

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
