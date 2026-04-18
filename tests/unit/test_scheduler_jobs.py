"""Unit tests for the four scheduler job modules.

Each job is tested in isolation with httpx.MockTransport / feedparser patches
so we avoid real network calls.
"""

from __future__ import annotations

import httpx
import pytest

from src.infrastructure.scheduler.jobs import (
    ateco_check as ateco_check_module,
)
from src.infrastructure.scheduler.jobs import (
    normativa_watchdog as watchdog_module,
)
from src.infrastructure.scheduler.jobs import (
    paf_delta as paf_delta_module,
)
from src.infrastructure.scheduler.jobs import (
    rag_reindex as rag_reindex_module,
)

# ──────────────────────── PAF delta ────────────────────────


@pytest.mark.asyncio
async def test_paf_delta_sync_ok(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "portaleagentifisici" in str(request.url)
        return httpx.Response(200, content=b"<html>PAF data</html>")

    transport = httpx.MockTransport(handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(paf_delta_module.httpx, "AsyncClient", _PatchedClient)

    result = await paf_delta_module.paf_delta_sync()

    assert result["status"] == "ok"
    assert int(result["fetched_bytes"]) > 0


@pytest.mark.asyncio
async def test_paf_delta_sync_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"boom")

    transport = httpx.MockTransport(handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(paf_delta_module.httpx, "AsyncClient", _PatchedClient)

    result = await paf_delta_module.paf_delta_sync()

    assert result["status"] == "error"


# ──────────────────────── ATECO check ────────────────────────


@pytest.mark.asyncio
async def test_ateco_check_up_to_date(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Publication about ATECO 2025 release")

    transport = httpx.MockTransport(handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ateco_check_module.httpx, "AsyncClient", _PatchedClient)
    monkeypatch.setenv("ATECO_LOCAL_VERSION", "2025")

    result = await ateco_check_module.ateco_check()

    assert result["status"] == "ok"
    assert result["remote_version"] == "2025"
    assert result["local_version"] == "2025"


@pytest.mark.asyncio
async def test_ateco_check_update_needed(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="New classification ATECO 2025 is out")

    transport = httpx.MockTransport(handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ateco_check_module.httpx, "AsyncClient", _PatchedClient)
    monkeypatch.setenv("ATECO_LOCAL_VERSION", "2022")

    result = await ateco_check_module.ateco_check()

    assert result["status"] == "update_needed"
    assert result["local_version"] == "2022"
    assert result["remote_version"] == "2025"


@pytest.mark.asyncio
async def test_ateco_check_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="")

    transport = httpx.MockTransport(handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ateco_check_module.httpx, "AsyncClient", _PatchedClient)

    result = await ateco_check_module.ateco_check()

    assert result["status"] == "error"


# ──────────────────────── Normativa watchdog ────────────────────────


SAMPLE_RSS_WITH_HIT = b"""<?xml version='1.0'?>
<rss version='2.0'>
<channel>
<title>Gazzetta</title>
<item>
<title>Nuovo decreto sul rumore negli ambienti di lavoro</title>
<description>Richiamo a ISO 9612 e D.Lgs. 81/2008</description>
<link>https://example.it/norm/1</link>
<guid>norm-1</guid>
</item>
<item>
<title>Aggiornamento generico</title>
<description>Niente a che vedere</description>
<link>https://example.it/other/1</link>
<guid>other-1</guid>
</item>
</channel>
</rss>
"""


@pytest.mark.asyncio
async def test_normativa_watchdog_filters_keywords(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=SAMPLE_RSS_WITH_HIT)

    transport = httpx.MockTransport(handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(watchdog_module.httpx, "AsyncClient", _PatchedClient)
    # Disable AuditLog DB writes for isolation
    monkeypatch.setattr(watchdog_module, "_record_audit", _noop_audit)

    # Restrict to a single source to keep assertions simple
    monkeypatch.setattr(
        watchdog_module,
        "SOURCES",
        {"gazzetta_ufficiale": "https://example.it/feed.xml"},
    )

    result = await watchdog_module.normativa_watchdog()

    assert result == {"gazzetta_ufficiale": 1}


@pytest.mark.asyncio
async def test_normativa_watchdog_handles_fetch_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"nope")

    transport = httpx.MockTransport(handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(watchdog_module.httpx, "AsyncClient", _PatchedClient)
    monkeypatch.setattr(watchdog_module, "_record_audit", _noop_audit)
    monkeypatch.setattr(
        watchdog_module,
        "SOURCES",
        {"gazzetta_ufficiale": "https://example.it/feed.xml"},
    )

    result = await watchdog_module.normativa_watchdog()

    assert result == {"gazzetta_ufficiale": 0}


def test_normativa_watchdog_filter_matches_case_insensitively():
    entries = [
        {
            "id": "1",
            "title": "Norme Acustica",
            "summary": "Riferimento a d.lgs. 81/2008 e ISO 9612",
            "link": "x",
            "published": "",
        },
        {
            "id": "2",
            "title": "Ambito fiscale",
            "summary": "Senza attinenza",
            "link": "y",
            "published": "",
        },
    ]
    matches = watchdog_module._filter_entries(entries)
    assert len(matches) == 1
    assert matches[0]["id"] == "1"
    assert "ISO 9612".lower() in [kw.lower() for kw in matches[0]["matched_keywords"]]


async def _noop_audit(*_args, **_kwargs):
    return None


# ──────────────────────── RAG reindex ────────────────────────


@pytest.mark.asyncio
async def test_rag_reindex_ok(monkeypatch):
    called: dict[str, bool] = {"invoked": False}

    async def fake_run_index(reset: bool = False):
        called["invoked"] = True
        assert reset is False
        return None

    # Simulate the real module being available
    import sys
    import types

    module = types.ModuleType("src.cli.index_paf_library")
    module.run_index = fake_run_index
    monkeypatch.setitem(sys.modules, "src.cli.index_paf_library", module)

    result = await rag_reindex_module.rag_reindex()

    assert result == {"status": "ok"}
    assert called["invoked"] is True


@pytest.mark.asyncio
async def test_rag_reindex_handles_indexer_failure(monkeypatch):
    async def failing_run_index(reset: bool = False):
        raise RuntimeError("chromadb unavailable")

    import sys
    import types

    module = types.ModuleType("src.cli.index_paf_library")
    module.run_index = failing_run_index
    monkeypatch.setitem(sys.modules, "src.cli.index_paf_library", module)

    result = await rag_reindex_module.rag_reindex()

    assert result["status"] == "error"
    assert "chromadb unavailable" in result["error"]
