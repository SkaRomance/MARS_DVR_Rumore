"""Monthly ATECO version check against an ISTAT endpoint.

If the remote version is newer than the locally known one, the job logs the
need for a re-seed. The full re-seed still runs through the dedicated CLI
(manual trigger for safety).
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

DEFAULT_ATECO_ENDPOINT = "https://www.istat.it/it/archivio/17888"
HTTP_TIMEOUT_S = 30.0


def _configured_endpoint() -> str:
    return os.getenv("ATECO_VERSION_ENDPOINT", DEFAULT_ATECO_ENDPOINT)


def _local_version() -> str:
    """Currently shipped ATECO version (data/ateco/ateco_2025.json)."""
    return os.getenv("ATECO_LOCAL_VERSION", "2025")


async def ateco_check() -> dict[str, str]:
    """Poll ATECO version endpoint; log if remote != local.

    Returns:
        dict with ``status`` ("ok" | "error" | "update_needed") and
        ``local_version`` / ``remote_version`` hints.
    """
    endpoint = _configured_endpoint()
    local_version = _local_version()
    logger.info("Starting ATECO version check against %s", endpoint)

    summary: dict[str, str] = {
        "status": "ok",
        "local_version": local_version,
        "remote_version": "",
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
            response = await client.get(
                endpoint,
                headers={"User-Agent": "MARS-Noise-Scheduler/0.1"},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("ATECO version fetch failed: %s", exc)
        summary["status"] = "error"
        summary["error"] = str(exc)[:200]
        return summary

    body = response.text or ""
    remote_version = _extract_remote_version(body, fallback=local_version)
    summary["remote_version"] = remote_version

    if remote_version != local_version:
        logger.warning(
            "ATECO update needed: local=%s remote=%s — run `python -m src.cli.seed_ateco_2025` to refresh",
            local_version,
            remote_version,
        )
        summary["status"] = "update_needed"
    else:
        logger.info("ATECO up to date (version=%s)", local_version)

    return summary


def _extract_remote_version(body: str, fallback: str) -> str:
    """Best-effort version extraction from the ISTAT landing page text."""
    for token in ("ATECO 2025", "ATECO 2022", "ATECO 2007"):
        if token in body:
            return token.split()[-1]
    return fallback
