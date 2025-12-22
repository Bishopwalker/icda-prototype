"""
Periodic Validation Scheduler.

Schedules Level 2 index validation at configurable intervals.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from .index_validator import IndexValidator
from .models import IndexHealthReport, SchedulerStatus

logger = logging.getLogger(__name__)


class ValidationScheduler:
    """
    Schedules periodic index validation.

    Default: Every 6 hours
    Can be triggered manually or on document upload threshold.
    """

    def __init__(
        self,
        validator: IndexValidator,
        interval_hours: int = 6,
        upload_threshold: int = 50,
    ):
        """
        Initialize the scheduler.

        Args:
            validator: IndexValidator instance
            interval_hours: Hours between automatic validations
            upload_threshold: Trigger validation after N uploads
        """
        self.validator = validator
        self.interval = timedelta(hours=interval_hours)
        self.upload_threshold = upload_threshold

        self.last_validation: Optional[datetime] = None
        self.next_validation: Optional[datetime] = None
        self.uploads_since_validation = 0
        self.reports: list[IndexHealthReport] = []

        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._get_chunks: Optional[Callable] = None

    async def start(self, get_chunks: Callable[[], list[dict]]) -> None:
        """
        Start the scheduler.

        Args:
            get_chunks: Callable that returns list of chunks to validate
        """
        self._running = True
        self._get_chunks = get_chunks
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Validation scheduler started (interval: {self.interval})")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Validation scheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            self.next_validation = datetime.utcnow() + self.interval

            try:
                await asyncio.sleep(self.interval.total_seconds())
            except asyncio.CancelledError:
                break

            if self._running and self._get_chunks:
                try:
                    await self._run_validation()
                except Exception as e:
                    logger.error(f"Scheduled validation failed: {e}")

    async def _run_validation(self) -> IndexHealthReport:
        """Run validation and store report."""
        logger.info("Running scheduled index validation...")

        chunks = self._get_chunks() if self._get_chunks else []
        report = await self.validator.validate_index(chunks)

        self.last_validation = datetime.utcnow()
        self.uploads_since_validation = 0
        self.reports.append(report)

        # Keep last 10 reports
        self.reports = self.reports[-10:]

        logger.info(
            f"Validation complete: health={report.health_score:.2f}, "
            f"duplicates={len(report.duplicate_clusters)}, "
            f"stale={len(report.stale_content)}"
        )

        return report

    def notify_upload(self) -> bool:
        """
        Called when a document is uploaded.

        Returns:
            bool: True if validation should be triggered
        """
        self.uploads_since_validation += 1
        return self.uploads_since_validation >= self.upload_threshold

    async def trigger_validation(self) -> Optional[IndexHealthReport]:
        """
        Manually trigger validation.

        Returns:
            IndexHealthReport or None if no chunks available
        """
        if not self._get_chunks:
            logger.warning("No chunk provider configured")
            return None

        return await self._run_validation()

    def get_status(self) -> SchedulerStatus:
        """Get scheduler status."""
        return SchedulerStatus(
            running=self._running,
            last_validation=self.last_validation.isoformat() if self.last_validation else None,
            next_validation=self.next_validation.isoformat() if self.next_validation else None,
            uploads_since_validation=self.uploads_since_validation,
            upload_threshold=self.upload_threshold,
            reports_count=len(self.reports),
            latest_health_score=self.reports[-1].health_score if self.reports else None,
        )

    def get_latest_report(self) -> Optional[IndexHealthReport]:
        """Get the most recent validation report."""
        return self.reports[-1] if self.reports else None

    def get_all_reports(self) -> list[IndexHealthReport]:
        """Get all stored validation reports."""
        return self.reports.copy()
