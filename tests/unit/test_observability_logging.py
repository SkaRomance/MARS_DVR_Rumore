"""Tests for structured logging configuration."""

import json
import logging

import pytest
import structlog

from src.infrastructure.observability.logging import configure_logging, get_logger


@pytest.fixture(autouse=True)
def reset_structlog():
    """Reset structlog defaults after each test."""
    yield
    structlog.reset_defaults()
    logging.getLogger().handlers.clear()


def test_configure_logging_emits_json(capsys):
    configure_logging(log_level="INFO", json_logs=True)
    logger = get_logger("test.json")
    logger.info("hello_world", user="alice", count=3)
    captured = capsys.readouterr().out.strip().splitlines()
    assert captured, "expected at least one log line on stdout"
    # Parse the last line (the test log entry).
    payload = json.loads(captured[-1])
    assert payload["event"] == "hello_world"
    assert payload["user"] == "alice"
    assert payload["count"] == 3
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_configure_logging_console_renderer(capsys):
    configure_logging(log_level="DEBUG", json_logs=False)
    logger = get_logger("test.console")
    logger.info("human_readable_event")
    out = capsys.readouterr().out
    assert "human_readable_event" in out
    # Console output is not JSON.
    with pytest.raises(json.JSONDecodeError):
        json.loads(out.strip().splitlines()[-1])


def test_configure_logging_respects_level(capsys):
    configure_logging(log_level="WARNING", json_logs=True)
    logger = get_logger("test.level")
    logger.info("should_be_filtered")
    logger.warning("should_appear")
    out = capsys.readouterr().out
    assert "should_be_filtered" not in out
    assert "should_appear" in out


def test_contextvars_are_merged(capsys):
    configure_logging(log_level="INFO", json_logs=True)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id="req-123")
    try:
        logger = get_logger("test.ctx")
        logger.info("bound_event")
        captured = capsys.readouterr().out.strip().splitlines()
        payload = json.loads(captured[-1])
        assert payload["request_id"] == "req-123"
    finally:
        structlog.contextvars.clear_contextvars()
