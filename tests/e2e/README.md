# End-to-end tests

Live-server tests that drive the plugin through its real HTTP surface.
They launch a `uvicorn` subprocess and a tiny FastAPI stub for MARS on
a neighbouring port, then exercise the autopilot pipeline, suggestion
approval, and the thin-plugin invariant via `httpx` (and optionally
Playwright for true browser flows).

All tests carry `@pytest.mark.e2e`. The default CI run excludes them:

```bash
pytest -m "not e2e"
```

## Prerequisites

```bash
pip install -e ".[test]"

# Chromium for the Playwright-based fixtures:
playwright install chromium
```

Required environment — handled automatically by the `uvicorn_server`
fixture, listed here for troubleshooting:

| Var                     | Value                                    |
| ----------------------- | ---------------------------------------- |
| `APP_ENV`               | `testing`                                |
| `DATABASE_URL`          | `sqlite+aiosqlite:///./test_e2e.db`      |
| `JWT_SECRET_KEY`        | `test-secret-e2e-only`                   |
| `MARS_API_BASE_URL`     | `http://127.0.0.1:8766`                  |
| `MARS_JWT_ALGORITHM`    | `HS256`                                  |
| `MARS_JWT_HS256_SECRET` | `test-secret-e2e-only`                   |

Ports 8765 (app) and 8766 (MARS mock) must be free.

## Run

```bash
# Headless (default):
pytest -m e2e tests/e2e/

# With a visible browser — uncomment headless=False in conftest or
# pass --headed through pytest-playwright:
pytest -m e2e tests/e2e/ --headed
```

## MARS mock scheme

The session-scoped `mars_mock_server` fixture runs a miniature FastAPI
app on port 8766 that implements just enough of MARS to let the plugin
work:

- `GET /me` → returns the test tenant + enabled `noise` module.
- `GET /companies/{id}` → returns a canned company.
- `GET /dvr/{id}` → returns a single-phase DVR payload with a
  `source_identification.completed: true` flag.

No persistence, no signature verification — the plugin's JWT validator
runs in HS256 mode against the shared `test-secret-e2e-only`.

## Tests

| File                               | What it checks                                              |
| ---------------------------------- | ----------------------------------------------------------- |
| `test_autopilot_flow.py`           | SSE event sequence from `/autopilot/{id}/run`.              |
| `test_suggestion_approval.py`      | Seed pending → approve via API → assert `status=approved`.  |
| `test_safe_editor.py`              | Direct DVR snapshot mutation must be rejected (skips if endpoint missing). |

## Troubleshooting

- **Port already in use** — another dev server is bound to 8765 or
  8766. Kill it or change the port constants at the top of `conftest.py`.
- **`uvicorn` subprocess dies immediately** — the fixture captures
  stdout+stderr; add a `print(proc.stdout.read())` in `conftest.py`
  before the `_wait_for` call to surface the traceback.
- **`test_e2e.db` locked** — leftover from a crash. The fixture
  deletes it at startup, but on Windows a zombie process can keep a
  handle open. Close and retry.
- **Playwright browser launch fails** — run `playwright install
  chromium` again; the test suite skips rather than fails when the
  browser is missing.
