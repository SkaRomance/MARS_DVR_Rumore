# Load tests — Locust

Targets the hot endpoints the frontend hits most often. Not part of
the default CI run; execute manually against a staging instance or a
locally running dev server.

## Run

```bash
pip install -e ".[test]"

# Start the app first (in another shell):
uvicorn src.bootstrap.main:app --port 8000

# Then spawn Locust with the web UI:
LOCUST_JWT="<paste a valid bearer token>" \
  locust -f tests/load/locustfile.py --host http://localhost:8000
```

Open http://localhost:8089 and start a swarm (e.g. 50 users, ramp 5/s).

For a headless run:

```bash
locust -f tests/load/locustfile.py \
       --host http://localhost:8000 \
       --headless \
       --users 50 --spawn-rate 5 \
       --run-time 2m \
       --csv results/locust
```

## Task mix

| Task                         | Weight | Notes                              |
| ---------------------------- | ------ | ---------------------------------- |
| `GET /health/ready`          | 10     | Dominates — mimics LB probe rate.  |
| `GET /contexts`              | 5      | Consultant-driven read.            |
| `GET /catalog/noise-sources` | 3      | UI dropdown refresh.               |
| `POST /contexts`             | 1      | Rare bootstrap write.              |

## Baseline targets

These are internal goals, not hard gates:

- `GET /health/ready`: p95 < 200 ms, p99 < 400 ms.
- `GET /contexts`: p95 < 500 ms under 50 concurrent users.
- `GET /catalog/noise-sources`: p95 < 300 ms (hits a cache-friendly
  read path once the catalog is warmed up).
- `POST /contexts`: p95 < 1500 ms (includes a MARS round-trip when
  `force_sync=true`; at `force_sync=false` it should stay under 500 ms).
- Error rate: < 0.5 % across all endpoints.

If p95 degrades, check:

1. Redis connectivity (the rate limiter becomes a no-op when Redis is
   unreachable but warnings flood the logs).
2. DB pool saturation (`asyncpg` pool size in settings).
3. MARS mock/upstream latency in the bootstrap path.
