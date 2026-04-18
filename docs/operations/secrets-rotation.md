# MARS DVR Rumore — Secrets Rotation

Rotate the long-lived secrets below on a predictable schedule (every 90
days unless stated) and immediately after any of:

- A secret has been seen by an AI coding agent.
- An ex-maintainer no longer has access.
- A suspected credential leak (public repo, log dump, clipboard, etc.).

## 1. Inventory

| Secret                         | Where used                                    | Scope / blast radius |
|--------------------------------|-----------------------------------------------|----------------------|
| `JWT_SECRET_KEY`               | Access + refresh token signing                | Invalidates all sessions |
| `DATABASE_URL`                 | PostgreSQL connection string                  | DB access            |
| `REDIS_URL`                    | Rate limiter backend                          | Rate limiting state  |
| `OLLAMA_API_KEY`               | LLM cloud provider                            | AI inference costs   |
| `KEYGEN_ADMIN_TOKEN`           | Licensing admin operations                    | License management   |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Optional fallback providers           | AI inference costs   |

All are injected via environment variables / secret manager — **never**
commit real values. The `.env` file in the repo is git-ignored but still
flows through local tooling; rotate after any AI-agent session that had
access to the repository checkout.

## 2. Rotation procedure (generic)

1. Generate a new value (see per-secret commands below).
2. Add the new value to the secret manager (AWS Secrets Manager / GCP
   Secret Manager / 1Password) under a versioned key.
3. Roll deployment with the new env var. Watch `/health/startup` and
   `/metrics` for errors.
4. Revoke the previous value in the upstream provider (DB role, Keygen
   admin token, LLM key).
5. Update any local `.env` files belonging to developers and re-run the
   test suite to confirm.

## 3. Per-secret notes

### JWT_SECRET_KEY

- Must be ≥ 32 random bytes. Generate with:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- Rotation **invalidates every outstanding access + refresh token**. Plan
  for a forced re-login or do a rolling rotation by supporting a second
  "next" key during a grace window.
- Production boot aborts (`RuntimeError`) if the key is still the
  placeholder `change-me-in-production` — see `src/bootstrap/main.py`
  lifespan.

### DATABASE_URL

- Rotate the DB user's password via `ALTER ROLE ... PASSWORD '<new>'`.
- Update the URL in the secret manager, then roll pods. SQLAlchemy
  connection pool will pick up the new credentials on next connection.
- Keep the old user active for < 1 hour after rollover for rollback, then
  revoke.

### REDIS_URL

- Redis is non-critical — the rate limiter degrades gracefully (permissive
  mode) if Redis is unreachable. Rotate with no downtime:
  1. Stand up the new Redis instance.
  2. Update `REDIS_URL`, deploy.
  3. Decommission the old instance.

### OLLAMA_API_KEY

- Issue a new key in the Ollama cloud console.
- Update the secret manager entry.
- Roll deployment; verify AI endpoints (POST `/api/v1/noise/ai/*`) return
  200.
- Revoke the previous key.

### KEYGEN_ADMIN_TOKEN

- Regenerate in the Keygen admin panel.
- Update secret and roll deployment.
- Revoke the previous token.

### OPENAI_API_KEY / ANTHROPIC_API_KEY

- Same pattern as Ollama. Optional fallbacks — service keeps working if
  these are absent (feature-flagged).

## 4. Verifying post-rotation

After every rotation:

1. `curl https://<host>/health/ready` → 200.
2. Smoke-test one AI endpoint (so the new LLM key is exercised).
3. Log in from a fresh client to confirm JWT signing works.
4. Scrape `/metrics` — look for a spike in `http_requests_total{status="5xx"}`.

## 5. Emergency revoke

If a secret is believed compromised:

1. **Revoke first, rotate second.** Kill the old credential upstream
   (disable DB user, revoke LLM key, delete Keygen token).
2. Force-logout all users by rotating `JWT_SECRET_KEY`.
3. Audit: `grep request_id=<suspect>` across recent logs + inspect the
   `audit_log` table for the affected window.

## 6. Related

- `docs/operations/runbook.md` — general ops playbook.
- `feedback_secrets.md` (memory) — project rule on AI-agent secret hygiene.
