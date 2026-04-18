"""Weekly re-index of the RAG ChromaDB collection.

Delegates to ``src.cli.index_paf_library.run_index`` when available. If the
module import fails (e.g. ChromaDB not installed in the running env), the
job logs a warning and returns status=``skipped`` so the scheduler keeps
serving other jobs.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def rag_reindex() -> dict[str, str]:
    """Re-index paf_library PDFs into ChromaDB.

    Returns:
        dict with ``status`` ("ok" | "error" | "skipped").
    """
    logger.info("Starting RAG re-index")
    try:
        from src.cli.index_paf_library import run_index
    except ImportError as exc:  # pragma: no cover — env-dependent
        logger.warning("RAG indexer not available (%s); skipping", exc)
        return {"status": "skipped", "reason": "indexer_unavailable"}

    try:
        await run_index(reset=False)
    except Exception as exc:
        logger.error("RAG re-index failed: %s", exc)
        return {"status": "error", "error": str(exc)[:200]}

    logger.info("RAG re-index completed")
    return {"status": "ok"}
