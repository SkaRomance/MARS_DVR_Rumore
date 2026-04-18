"""Unit tests for the scheduler runner (build / start / stop lifecycle)."""

from __future__ import annotations

import asyncio

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.infrastructure.scheduler.runner import (
    build_scheduler,
    start_scheduler,
    stop_scheduler,
)


def test_build_scheduler_returns_async_io_scheduler():
    scheduler = build_scheduler()
    assert isinstance(scheduler, AsyncIOScheduler)
    assert not scheduler.running


def test_build_scheduler_registers_all_four_jobs():
    scheduler = build_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert job_ids == {"paf_delta", "ateco_check", "normativa_watchdog", "rag_reindex"}


def test_build_scheduler_honors_timezone_argument():
    scheduler = build_scheduler(timezone="UTC")
    assert str(scheduler.timezone) == "UTC"


def test_build_scheduler_default_timezone_is_europe_rome():
    scheduler = build_scheduler()
    assert str(scheduler.timezone) == "Europe/Rome"


def test_job_defaults_prevent_overlap_and_coalesce():
    scheduler = build_scheduler()
    defaults = scheduler._job_defaults  # APScheduler exposes these
    assert defaults["coalesce"] is True
    assert defaults["max_instances"] == 1
    assert defaults["misfire_grace_time"] == 3600


@pytest.mark.asyncio
async def test_start_and_stop_scheduler_lifecycle():
    """Start the scheduler in a running event loop and stop it cleanly."""
    scheduler = build_scheduler()
    assert not scheduler.running

    start_scheduler(scheduler)
    try:
        assert scheduler.running
        # Give the scheduler a tick to settle
        await asyncio.sleep(0.05)
    finally:
        stop_scheduler(scheduler)

    # After shutdown(wait=False), APScheduler transitions state asynchronously;
    # yield to the event loop so the transition can complete.
    await asyncio.sleep(0.05)
    assert not scheduler.running


def test_stop_scheduler_is_safe_when_not_running():
    scheduler = build_scheduler()
    # Must not raise even though scheduler was never started
    stop_scheduler(scheduler)
    assert not scheduler.running
