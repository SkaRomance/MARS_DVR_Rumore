"""Structured logging configuration using structlog.

Produces JSON logs in production and a human-friendly renderer in development.
The bound context (correlation ids, tenant ids, etc.) is preserved across
async boundaries via `structlog.contextvars` so every log line emitted during
a request carries the same correlation metadata.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.types import Processor


def _build_processors(*, json_logs: bool) -> list[Processor]:
    """Build the processor chain shared by structlog and stdlib loggers."""
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_logs:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer(colors=False))
    return shared_processors


def configure_logging(*, log_level: str = "INFO", json_logs: bool = True) -> None:
    """Configure structlog and the root stdlib logger.

    Args:
        log_level: Minimum log level name (e.g. ``"INFO"``).
        json_logs: When True emits JSON lines; when False uses the console
            renderer. Production should always use JSON.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    processors = _build_processors(json_logs=json_logs)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through the same stream so third-party libraries
    # (uvicorn, sqlalchemy, httpx) emit in the configured format.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Silence overly chatty loggers in production.
    for noisy in ("sqlalchemy.engine", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger, optionally named."""
    return structlog.get_logger(name) if name else structlog.get_logger()
