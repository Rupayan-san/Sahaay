from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.notification_service import get_notification_service
from app.services.report_generator import get_report_generator_service

logger = logging.getLogger(__name__)

WEEKLY_REPORT_JOB_ID = "weekly-impact-report"
WEEKLY_REPORT_HOUR_UTC = 8

_scheduler: AsyncIOScheduler | None = None


async def start_scheduled_reports() -> None:
    global _scheduler

    if _scheduler is not None:
        return

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _run_weekly_impact_report_job,
        trigger=CronTrigger(day_of_week="mon", hour=WEEKLY_REPORT_HOUR_UTC, minute=0, timezone="UTC"),
        id=WEEKLY_REPORT_JOB_ID,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduled weekly impact reports for Mondays at %s:00 UTC", WEEKLY_REPORT_HOUR_UTC)


async def stop_scheduled_reports() -> None:
    global _scheduler

    if _scheduler is None:
        return

    scheduler = _scheduler
    _scheduler = None
    await asyncio.to_thread(scheduler.shutdown, wait=False)
    logger.info("Stopped scheduled report jobs")


async def _run_weekly_impact_report_job() -> None:
    try:
        report = await get_report_generator_service().generate_weekly_impact_report(days=7)
        html_body = get_report_generator_service().render_markdown_as_html(report.report_markdown)
        subject = f"Weekly Impact Report - {report.date_range}"
        await get_notification_service().notify_admin(
            subject=subject,
            body=report.report_markdown,
            html_body=html_body,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Weekly impact report job failed")
