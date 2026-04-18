"""Daily watchdog: polls Gazzetta Ufficiale + EUR-Lex RSS for noise-related updates.

Matches on a small Italian keyword list. Hits are logged and (optionally)
recorded as AuditLog entries. No separate ``normativa_update`` table is
created — kept out of scope for the reduced Wave 28.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx

from src.bootstrap.database import get_session_factory
from src.infrastructure.database.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

KEYWORDS: tuple[str, ...] = (
    "rumore",
    "D.Lgs. 81/2008",
    "d.lgs. 81/2008",
    "decreto legislativo 81",
    "ISO 9612",
    "iso 9612",
    "acustica",
    "esposizione rumore",
)

SOURCES: dict[str, str] = {
    "gazzetta_ufficiale": "https://www.gazzettaufficiale.it/rss/atti_generali.xml",
    "eur_lex": "https://eur-lex.europa.eu/rss/news.xml",
}

HTTP_TIMEOUT_S = 30.0


async def normativa_watchdog() -> dict[str, int]:
    """Fetch configured RSS feeds and log any keyword hits.

    Returns:
        dict mapping source name → number of matched entries.
    """
    logger.info("Starting normativa watchdog")
    hits_per_source: dict[str, int] = {}

    for source_name, url in SOURCES.items():
        try:
            entries = await _fetch_feed(url)
        except httpx.HTTPError as exc:
            logger.error("Feed fetch failed for %s: %s", source_name, exc)
            hits_per_source[source_name] = 0
            continue

        matches = _filter_entries(entries)
        hits_per_source[source_name] = len(matches)

        if matches:
            logger.info(
                "Normativa watchdog: %d match(es) on %s",
                len(matches),
                source_name,
            )
            await _record_audit(source_name, matches)

    total = sum(hits_per_source.values())
    logger.info("Normativa watchdog done: %d matches across %d sources", total, len(SOURCES))
    return hits_per_source


async def _fetch_feed(url: str) -> list[dict[str, Any]]:
    """Fetch an RSS/Atom feed and return parsed entries as dicts.

    feedparser is sync; we run it on the fetched bytes (already async-fetched)
    and convert to a plain list of dicts so tests can easily assert.
    """
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
        response = await client.get(
            url,
            headers={"User-Agent": "MARS-Noise-Watchdog/0.1"},
        )
        response.raise_for_status()

    parsed = feedparser.parse(response.content)
    entries: list[dict[str, Any]] = []
    for entry in parsed.entries or []:
        entries.append(
            {
                "id": getattr(entry, "id", getattr(entry, "link", "")),
                "title": getattr(entry, "title", ""),
                "summary": getattr(entry, "summary", ""),
                "link": getattr(entry, "link", ""),
                "published": getattr(entry, "published", ""),
            }
        )
    return entries


def _filter_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return entries whose title or summary contains any configured keyword."""
    matches: list[dict[str, Any]] = []
    for entry in entries:
        combined = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
        matched = [kw for kw in KEYWORDS if kw.lower() in combined]
        if matched:
            entry_copy = dict(entry)
            entry_copy["matched_keywords"] = matched
            matches.append(entry_copy)
    return matches


async def _record_audit(source_name: str, matches: list[dict[str, Any]]) -> None:
    """Record matches as audit log entries (best-effort; swallow DB errors)."""
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            for match in matches:
                session.add(
                    AuditLog(
                        action="normativa_watchdog.match",
                        resource_type="normativa_feed",
                        resource_id=(match.get("id") or "")[:36] or None,
                        details={
                            "source": source_name,
                            "title": match.get("title", "")[:500],
                            "link": match.get("link", ""),
                            "matched_keywords": match.get("matched_keywords", []),
                            "fetched_at": datetime.now(UTC).isoformat(),
                        },
                    )
                )
            await session.commit()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Audit log write failed (non-fatal): %s", exc)
