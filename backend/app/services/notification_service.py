from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from functools import lru_cache

from app.core.config import get_settings
from app.services.matching_engine import get_matching_engine

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


class NotificationService:
    """Send volunteer email notifications for high-priority issues."""

    async def notify_high_priority_issue(self, issue_identifier: str, *, notification_limit: int = 5) -> None:
        settings = get_settings()
        if not settings.gmail_user or not settings.gmail_app_password:
            logger.warning("Skipping email notifications because Gmail SMTP credentials are not configured")
            return

        matching_engine = get_matching_engine()

        try:
            issue_record = await matching_engine.get_issue_record(issue_identifier)
            matches = await matching_engine.match_issue(issue_identifier, limit=notification_limit)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to prepare high-priority notifications for issue %s", issue_identifier)
            return

        if not matches:
            logger.info("No volunteer matches found for high-priority issue %s", issue_identifier)
            return

        tasks = [
            asyncio.create_task(
                self.send_email_message(
                    recipient_email=match.email,
                    subject=f"New high-priority issue in {issue_record.location}: {issue_record.title}",
                    body=(
                        f"Hello {match.name},\n\n"
                        f"You might be a good match for this issue.\n\n"
                        f"Title: {issue_record.title}\n"
                        f"Location: {issue_record.location}\n"
                        f"Priority score: {issue_record.priority_score}\n"
                        f"Description: {issue_record.description}\n\n"
                        "Please check the platform for next steps."
                    ),
                )
            )
            for match in matches
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def notify_admin(self, subject: str, body: str, *, html_body: str | None = None) -> None:
        settings = get_settings()
        recipient = settings.admin_notification_email or settings.gmail_user
        if not recipient:
            logger.warning("Skipping admin notification because no recipient email is configured")
            return
        await self.send_email_message(
            recipient_email=recipient,
            subject=subject,
            body=body,
            html_body=html_body,
        )

    async def notify_recipient(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        *,
        html_body: str | None = None,
    ) -> None:
        await self.send_email_message(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            html_body=html_body,
        )

    async def send_email_message(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None:
        try:
            await asyncio.to_thread(self._send_email_sync, recipient_email, subject, body, html_body)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to send email notification to %s", recipient_email)

    def _send_email_sync(self, recipient_email: str, subject: str, body: str, html_body: str | None = None) -> None:
        settings = get_settings()
        if not settings.gmail_user or not settings.gmail_app_password:
            raise RuntimeError("Gmail SMTP credentials are not configured")

        message = EmailMessage()
        message["From"] = settings.gmail_user
        message["To"] = recipient_email
        message["Subject"] = subject
        message.set_content(body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(settings.gmail_user, settings.gmail_app_password)
            smtp.send_message(message)


@lru_cache(maxsize=1)
def get_notification_service() -> NotificationService:
    return NotificationService()
