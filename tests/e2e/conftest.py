"""E2E test fixtures — live uvicorn subprocess + MARS mock.

All E2E tests carry the `@pytest.mark.e2e` marker so CI can skip them
via `-m "not e2e"`. They require:

* Chromium installed for Playwright (`playwright install chromium`).
* Free TCP ports 8765 (app) and 8766 (MARS mock).
* A writable CWD for the SQLite file `./test_e2e.db`.

The MARS mock is an in-process FastAPI app served on a background
thread via uvicorn; it returns the bare minimum the plugin needs to
resolve tenant context and fetch DVR snapshots — no persistence, no
signature verification, no realism beyond shape.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

APP_PORT = 8765
MARS_MOCK_PORT = 8766
APP_BASE_URL = f"http://127.0.0.1:{APP_PORT}"
MARS_BASE_URL = f"http://127.0.0.1:{MARS_MOCK_PORT}"

# Shared test tenant id — the MARS mock echoes this in /me and the test
# DB row is created to match so the plugin accepts the requests.
TEST_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-00000000cafe")
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000042")
TEST_JWT_SECRET = "test-secret-e2e-only"  # noqa: S105 — test fixture only


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _wait_for(url: str, timeout_seconds: float = 30.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code < 500:
                return
        except (httpx.HTTPError, OSError):
            pass
        time.sleep(0.3)
    raise RuntimeError(f"Timed out waiting for {url}")


def _build_mars_mock_app():
    """Minimal FastAPI app that stands in for MARS endpoints."""
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/me")
    async def me():
        return {
            "user_id": str(TEST_USER_ID),
            "tenant_id": str(TEST_TENANT_ID),
            "email": "e2e@test.local",
            "enabled_modules": ["noise"],
            "role": "admin",
        }

    @app.get("/companies/{company_id}")
    async def company(company_id: str):
        return {
            "id": company_id,
            "name": "E2E Company Srl",
            "vat_number": "IT00000000000",
            "ateco": "25.99.99",
        }

    @app.get("/dvr/{dvr_id}")
    async def dvr(dvr_id: str):
        return {
            "id": dvr_id,
            "company_id": str(TEST_COMPANY_ID),
            "phases": [
                {
                    "id": "p1",
                    "name": "Taglio metallo",
                    "description": "Taglio con flex su banco",
                    "equipments": [{"type": "angle_grinder", "model": "Flex LBR"}],
                    "job_role": "operaio_metalmeccanico",
                }
            ],
            "source_identification": {"completed": True},
        }

    return app


@pytest.fixture(scope="session")
def mars_mock_server() -> Generator[str, None, None]:
    """Run the MARS mock FastAPI app on port 8766 for the whole session."""
    import uvicorn

    app = _build_mars_mock_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=MARS_MOCK_PORT, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_for(f"{MARS_BASE_URL}/me", timeout_seconds=15.0)

    yield MARS_BASE_URL

    server.should_exit = True
    thread.join(timeout=5.0)


@pytest.fixture(scope="session")
def uvicorn_server(mars_mock_server: str) -> Generator[str, None, None]:
    """Launch the real app in a subprocess bound to APP_PORT."""
    if _port_open("127.0.0.1", APP_PORT):
        raise RuntimeError(f"Port {APP_PORT} already in use — stop the other process first")

    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "testing",
            "DATABASE_URL": "sqlite+aiosqlite:///./test_e2e.db",
            "JWT_SECRET_KEY": TEST_JWT_SECRET,
            "MARS_API_BASE_URL": mars_mock_server,
            "MARS_JWT_ALGORITHM": "HS256",
            "MARS_JWT_HS256_SECRET": TEST_JWT_SECRET,
            "MARS_ISSUER": "e2e-test",
            "MARS_AUDIENCE": "mars-plugin",
        }
    )

    # Clean leftover db from a previous failed run.
    db_file = Path("./test_e2e.db")
    if db_file.exists():
        db_file.unlink()

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.bootstrap.main:app",
            "--port",
            str(APP_PORT),
            "--host",
            "127.0.0.1",
            "--log-level",
            "warning",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        _wait_for(f"{APP_BASE_URL}/health/ready", timeout_seconds=45.0)
    except Exception:
        proc.terminate()
        raise

    yield APP_BASE_URL

    proc.terminate()
    try:
        proc.wait(timeout=10.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5.0)

    if db_file.exists():
        try:
            db_file.unlink()
        except OSError:
            pass


def _make_test_jwt(tenant_id: uuid.UUID = TEST_TENANT_ID) -> str:
    """Issue a JWT the plugin's MARS validator accepts in HS256 mode."""
    import jwt

    claims = {
        "sub": str(TEST_USER_ID),
        "tenant_id": str(tenant_id),
        "email": "e2e@test.local",
        "iss": "e2e-test",
        "aud": "mars-plugin",
        "enabled_modules": ["noise"],
        "role": "admin",
    }
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture(scope="session")
def test_jwt() -> str:
    return _make_test_jwt()


@pytest.fixture(scope="session")
def auth_headers(test_jwt: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {test_jwt}"}


@pytest_asyncio.fixture
async def http_client(
    uvicorn_server: str, auth_headers: dict[str, str]
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        base_url=uvicorn_server, headers=auth_headers, timeout=30.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def playwright_page(uvicorn_server: str):
    """Launch Chromium and navigate to the frontend root.

    Skips gracefully if Playwright isn't installed in the environment.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("playwright not installed — run `pip install playwright && playwright install`")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium launch failed: {exc}")

        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(f"{uvicorn_server}/static/")

        yield page

        await context.close()
        await browser.close()
