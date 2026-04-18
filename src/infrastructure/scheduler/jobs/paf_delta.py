"""PAF (Portale Agenti Fisici) weekly delta sync.

Best-effort httpx fetch of the PAF machine-database index. For each entry
matched, the NoiseSourceCatalog row is upserted with a refreshed
``data_aggiornamento`` marker.

This is a stub: the PAF website does not expose a structured JSON feed. A real
implementation would drive the existing scraping CLI (``run_paf_noise.ps1``)
or a Python port of it. The job here keeps the scheduler wiring honest and
lets us mock httpx in tests.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

PAF_DELTA_URL = "https://www.portaleagentifisici.it/fo_ra_ind_macchine.php?lg=IT"
HTTP_TIMEOUT_S = 30.0


async def paf_delta_sync() -> dict[str, int | str]:
    """Fetch PAF catalog and return a summary dict.

    Returns:
        dict with keys ``status`` ("ok" | "error" | "skipped") and
        ``fetched_bytes`` (int).
    """
    logger.info("Starting PAF delta sync")
    summary: dict[str, int | str] = {"status": "skipped", "fetched_bytes": 0}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
            response = await client.get(
                PAF_DELTA_URL,
                headers={"User-Agent": "MARS-Noise-Scheduler/0.1"},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("PAF delta fetch failed: %s", exc)
        summary["status"] = "error"
        summary["error"] = str(exc)[:200]
        return summary

    body = response.content or b""
    summary["fetched_bytes"] = len(body)
    summary["status"] = "ok"

    # NOTE: a real implementation would parse `body` and upsert rows in
    # NoiseSourceCatalog here. Kept as a log-only stub.
    logger.info("PAF delta sync completed (%d bytes downloaded)", len(body))
    return summary
