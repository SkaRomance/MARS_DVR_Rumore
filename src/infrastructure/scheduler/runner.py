"""In-process APScheduler runner.

Started/stopped inside the FastAPI lifespan (see src/bootstrap/main.py).
Controlled by the SCHEDULER_ENABLED env var (default: off).

Jobs registered:
  * paf_delta           — weekly cron  (Sun 03:00 Europe/Rome)
  * ateco_check         — monthly cron (day 1, 04:00 Europe/Rome)
  * normativa_watchdog  — daily cron   (07:15 Europe/Rome)
  * rag_reindex         — weekly cron  (Sat 05:00 Europe/Rome)

The scheduler uses MemoryJobStore (no Redis / DB dependency). If a distributed
scheduler is needed later, swap the jobstore in build_scheduler().
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.infrastructure.scheduler.jobs.ateco_check import ateco_check
from src.infrastructure.scheduler.jobs.normativa_watchdog import normativa_watchdog
from src.infrastructure.scheduler.jobs.paf_delta import paf_delta_sync
from src.infrastructure.scheduler.jobs.rag_reindex import rag_reindex

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Europe/Rome"


def build_scheduler(timezone: str = DEFAULT_TIMEZONE) -> AsyncIOScheduler:
    """Create an AsyncIOScheduler with the MARS noise jobs registered.

    The scheduler is NOT started — caller is expected to call `.start()` /
    `.shutdown()` (typically from a FastAPI lifespan).
    """
    scheduler = AsyncIOScheduler(
        timezone=timezone,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        },
    )

    scheduler.add_job(
        paf_delta_sync,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="paf_delta",
        replace_existing=True,
    )

    scheduler.add_job(
        ateco_check,
        CronTrigger(day=1, hour=4, minute=0),
        id="ateco_check",
        replace_existing=True,
    )

    scheduler.add_job(
        normativa_watchdog,
        CronTrigger(hour=7, minute=15),
        id="normativa_watchdog",
        replace_existing=True,
    )

    scheduler.add_job(
        rag_reindex,
        CronTrigger(day_of_week="sat", hour=5, minute=0),
        id="rag_reindex",
        replace_existing=True,
    )

    return scheduler


def start_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Start scheduler and log registered jobs."""
    scheduler.start()
    job_ids = [j.id for j in scheduler.get_jobs()]
    logger.info("Scheduler started with jobs: %s", job_ids)


def stop_scheduler(scheduler: AsyncIOScheduler, wait: bool = False) -> None:
    """Shutdown scheduler gracefully.

    Args:
        scheduler: the running AsyncIOScheduler.
        wait: if True, blocks until running jobs complete; defaults False so
            the FastAPI lifespan can exit promptly.
    """
    if scheduler.running:
        scheduler.shutdown(wait=wait)
        logger.info("Scheduler stopped (wait=%s)", wait)
