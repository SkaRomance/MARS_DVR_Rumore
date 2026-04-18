# MARS DVR Rumore — Operations Runbook

Quick-reference for common operational tasks. Keep short, add a new
section instead of growing existing ones when procedures diverge.

## 1. Health & readiness

The service exposes four endpoints under `/health`:

| Endpoint            | Purpose                               | Healthy status |
|---------------------|---------------------------------------|----------------|
| `GET /health/`      | Legacy aggregated status              | 200 healthy / degraded, 503 unhealthy |
| `GET /health/live`  | Liveness probe (no DB hit)            | Always 200 while process runs |
| `GET /health/ready` | Readiness probe (DB + Redis check)    | 200 when DB ok, 503 when DB down |
| `GET /health/startup` | Startup probe                       | 503 until bootstrap done, 200 after |

Redis failure is treated as a soft degradation on `/health/ready` because
rate limiting falls back to a permissive limiter when Redis is missing.

## 2. Metrics

Prometheus metrics at `GET /metrics`. The default instrumentator exposes:

- `http_requests_total{handler,method,status}`
- `http_request_duration_seconds{handler,method}`
- Standard Python process metrics (`process_*`, `python_gc_*`).

Probes (`/health/live`, `/health/ready`, `/health/startup`) and `/metrics`
itself are excluded from the histograms.

Scrape example (Prometheus):

```yaml
- job_name: mars-noise
  static_configs:
    - targets: ["mars-api.internal:8000"]
  metrics_path: /metrics
  scrape_interval: 15s
```

## 3. Structured logs

All log output is JSON in production (`APP_ENV != development`). Fields:

- `timestamp` — ISO-8601 UTC
- `level` — `info`, `warning`, `error`, ...
- `event` — the log event key (e.g. `app_startup_complete`)
- `request_id` — correlation id (present when emitted during a request)

Aggregate with Loki / CloudWatch / ELK using `request_id` to tie related
log lines together across services.

## 4. Correlation IDs

Every request receives an `X-Request-ID` header. Clients may provide one
and it will be echoed back; otherwise the server generates a UUID4.

When investigating an incident reported by a user, ask for the
`X-Request-ID` header value from any response — logs can be filtered
directly by it.

## 5. Common tasks

### Tail logs of a running instance

```bash
# Kubernetes
kubectl logs -f -l app=mars-noise --tail=200

# Docker
docker logs -f mars-noise
```

### Restart rate-limiter after Redis recovery

The rate limiter auto-detects Redis at startup. If Redis was down when the
app booted, the limiter stays in permissive mode until restart.

```bash
kubectl rollout restart deploy/mars-noise   # K8s
docker compose restart api                  # Compose
```

### Create the first admin user

```bash
create-admin --email ops@example.com --password <strong-password>
```

See `src/cli/create_admin.py` for flags.

### Run database migrations

```bash
alembic upgrade head
```

Review `migrations/` for the revision list. Always take a DB snapshot
before applying a migration in production.

## 6. Incident triage quick sheet

| Symptom                                   | First check |
|-------------------------------------------|-------------|
| 5xx spike                                 | `/health/ready` + `http_requests_total{status=~"5.."}` |
| Slow responses                            | `http_request_duration_seconds` p95 / p99 per handler |
| Auth failures surge                       | Audit log entries, `user_id`/`tenant_id` in JSON logs |
| AI endpoints timing out                   | Ollama cloud provider status, check `ai_*` log events |
| Rate limiter blocking legit traffic       | `rate_limiter` log events, confirm Redis health       |

## 7. Rolling a breaking change

1. Merge behind a feature flag when possible (environment variable).
2. Deploy to staging, run the API smoke tests.
3. Verify `/health/startup` returns 200 within the configured timeout.
4. Scrape `/metrics` from the staging instance for ≥ 5 minutes — compare
   p95 latency to the previous baseline.
5. Promote to production with a canary (1 pod / 10% traffic) before a
   full rollout.

## 8. Related docs

- `docs/operations/secrets-rotation.md` — JWT, DB, Keygen, Ollama keys.
- `AGENTS.md` — codebase map for AI assistants.
- `CORE_PROTOCOL.md` — project invariants.
