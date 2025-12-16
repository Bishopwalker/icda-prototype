"""
Gemini Enforcer - Main Integration Class.

Coordinates all three enforcement levels and provides unified API.

Level 1: Chunk Quality Gate (pre-index)
Level 2: Index Validation (periodic)
Level 3: Query Review (runtime)
"""

import logging
from typing import Any, Callable, Optional

from .client import GeminiClient, GeminiConfig
from .chunk_gate import ChunkQualityGate
from .index_validator import IndexValidator
from .query_reviewer import QueryReviewer
from .scheduler import ValidationScheduler
from .models import (
    ChunkQualityScore,
    ChunkGateResult,
    IndexHealthReport,
    QueryReviewResult,
    EnforcerMetrics,
)

logger = logging.getLogger(__name__)


class GeminiEnforcer:
    """
    Main Gemini Enforcer - coordinates all 3 levels of enforcement.

    Usage:
        enforcer = GeminiEnforcer()

        # Level 1: Pre-index
        result = await enforcer.evaluate_chunk(chunk_id, content)

        # Level 2: Periodic
        report = await enforcer.validate_index(chunks)

        # Level 3: Runtime
        review = await enforcer.review_query(query_id, query, chunks, response)

        # Metrics
        metrics = enforcer.get_metrics()
    """

    def __init__(
        self,
        config: Optional[GeminiConfig] = None,
        chunk_threshold: float = 0.6,
        query_sample_rate: float = 0.1,
        validation_interval_hours: int = 6,
    ):
        """
        Initialize the Gemini Enforcer.

        Args:
            config: Gemini client configuration
            chunk_threshold: Min quality score for chunks (Level 1)
            query_sample_rate: Fraction of queries to review (Level 3)
            validation_interval_hours: Hours between validations (Level 2)
        """
        self.client = GeminiClient(config)
        self.available = self.client.available

        # Initialize enforcement levels
        self.chunk_gate = ChunkQualityGate(
            self.client,
            threshold=chunk_threshold,
        )

        self.index_validator = IndexValidator(self.client)

        self.query_reviewer = QueryReviewer(
            self.client,
            sample_rate=query_sample_rate,
        )

        self.scheduler = ValidationScheduler(
            self.index_validator,
            interval_hours=validation_interval_hours,
        )

        self._metrics = EnforcerMetrics()

    # ==================== Level 1: Chunk Quality Gate ====================

    async def evaluate_chunk(
        self,
        chunk_id: str,
        content: str,
        source: str = "unknown",
        content_type: str = "text",
    ) -> dict[str, Any]:
        """
        Level 1: Evaluate a single chunk before indexing.

        Args:
            chunk_id: Unique chunk identifier
            content: Chunk text content
            source: Source filename
            content_type: Type of content

        Returns:
            Dict with approval status and scores
        """
        if not self.available:
            return {"approved": True, "reason": "Enforcer disabled"}

        result = await self.chunk_gate.evaluate_chunk(
            chunk_id, content, source, content_type
        )

        # Update metrics
        self._metrics.chunks_processed += 1
        if result.approved:
            self._metrics.chunks_approved += 1
        else:
            self._metrics.chunks_rejected += 1

        # Update running average
        n = self._metrics.chunks_processed
        self._metrics.avg_chunk_quality = (
            (self._metrics.avg_chunk_quality * (n - 1) + result.overall) / n
        )

        return {
            "approved": result.approved,
            "overall_score": result.overall,
            "coherence": result.coherence,
            "completeness": result.completeness,
            "relevance": result.relevance,
            "rejection_reason": result.rejection_reason,
            "improvements": result.improvements,
            "processing_ms": result.processing_ms,
        }

    async def evaluate_chunks_batch(
        self,
        chunks: list[dict[str, Any]],
    ) -> ChunkGateResult:
        """
        Level 1: Evaluate a batch of chunks.

        Args:
            chunks: List of chunk dicts with 'chunk_id', 'content', etc.

        Returns:
            ChunkGateResult with all evaluations
        """
        if not self.available:
            # Return all approved when disabled
            return ChunkGateResult(
                total_processed=len(chunks),
                approved=len(chunks),
                rejected=0,
                improved=0,
                scores=[
                    ChunkQualityScore(
                        chunk_id=c.get("chunk_id", f"chunk_{i}"),
                        coherence=0.8,
                        completeness=0.8,
                        relevance=0.8,
                        overall=0.8,
                        approved=True,
                    )
                    for i, c in enumerate(chunks)
                ],
                avg_coherence=0.8,
                avg_completeness=0.8,
                avg_relevance=0.8,
                processing_time_ms=0,
            )

        result = await self.chunk_gate.evaluate_batch(chunks)

        # Update metrics
        self._metrics.chunks_processed += result.total_processed
        self._metrics.chunks_approved += result.approved
        self._metrics.chunks_rejected += result.rejected

        return result

    # ==================== Level 2: Index Validation ====================

    async def validate_index(
        self,
        chunks: list[dict[str, Any]],
    ) -> IndexHealthReport:
        """
        Level 2: Run full index validation.

        Args:
            chunks: List of chunk dicts to validate

        Returns:
            IndexHealthReport with findings
        """
        if not self.available:
            return IndexHealthReport(
                total_chunks=len(chunks),
                health_score=1.0,
                recommendations=["Enforcer disabled - validation skipped"],
            )

        report = await self.index_validator.validate_index(chunks)

        # Update metrics
        self._metrics.validations_run += 1
        self._metrics.current_health_score = report.health_score
        self._metrics.duplicates_found += len(report.duplicate_clusters)
        self._metrics.stale_content_found += len(report.stale_content)

        return report

    async def start_scheduler(self, get_chunks: Callable[[], list[dict]]) -> None:
        """
        Start periodic validation scheduler.

        Args:
            get_chunks: Callable that returns chunks to validate
        """
        if self.available:
            await self.scheduler.start(get_chunks)

    async def stop_scheduler(self) -> None:
        """Stop periodic validation scheduler."""
        await self.scheduler.stop()

    def notify_upload(self) -> bool:
        """
        Notify of document upload.

        Returns:
            bool: True if threshold reached and validation needed
        """
        return self.scheduler.notify_upload()

    # ==================== Level 3: Query Review ====================

    async def review_query(
        self,
        query_id: str,
        query_text: str,
        retrieved_chunks: list[dict[str, Any]],
        response_text: str,
        force: bool = False,
    ) -> Optional[QueryReviewResult]:
        """
        Level 3: Review a query/response pair.

        Only reviews a sample of queries unless force=True.

        Args:
            query_id: Unique query identifier
            query_text: The user's query
            retrieved_chunks: Chunks used for context
            response_text: AI-generated response
            force: Force review (bypass sampling)

        Returns:
            QueryReviewResult or None if not sampled
        """
        if not self.available:
            return None

        if not force and not self.query_reviewer.should_review():
            return None

        result = await self.query_reviewer.review_query(
            query_id, query_text, retrieved_chunks, response_text
        )

        # Update metrics
        self._metrics.queries_reviewed += 1
        if result.hallucination_detected:
            self._metrics.hallucinations_detected += 1

        # Update running averages
        n = self._metrics.queries_reviewed
        self._metrics.avg_accuracy = (
            (self._metrics.avg_accuracy * (n - 1) + result.accuracy_score) / n
        )
        self._metrics.avg_grounding = (
            (self._metrics.avg_grounding * (n - 1) + result.grounding_score) / n
        )

        return result

    # ==================== Metrics & Status ====================

    def get_metrics(self) -> dict[str, Any]:
        """Get aggregated metrics from all levels."""
        return {
            "available": self.available,
            "model": self.client.config.model if self.client.config else "unknown",
            **self._metrics.to_dict(),
            "scheduler": {
                "running": self.scheduler._running,
                "last_validation": (
                    self.scheduler.last_validation.isoformat()
                    if self.scheduler.last_validation else None
                ),
                "next_validation": (
                    self.scheduler.next_validation.isoformat()
                    if self.scheduler.next_validation else None
                ),
                "uploads_since_validation": self.scheduler.uploads_since_validation,
            },
        }

    def get_detailed_stats(self) -> dict[str, Any]:
        """Get detailed stats from all components."""
        return {
            "available": self.available,
            "chunk_gate": self.chunk_gate.get_stats(),
            "index_validator": self.index_validator.get_stats(),
            "query_reviewer": self.query_reviewer.get_stats(),
            "scheduler": self.scheduler.get_status().__dict__,
        }

    def get_problem_patterns(self) -> list[dict[str, Any]]:
        """Get query patterns with consistently low quality."""
        patterns = self.query_reviewer.get_problem_patterns()
        return [
            {
                "pattern": p.pattern,
                "frequency": p.frequency,
                "avg_quality": p.avg_quality,
                "common_issues": p.common_issues,
            }
            for p in patterns
        ]

    async def close(self) -> None:
        """Cleanup resources."""
        await self.stop_scheduler()
        await self.client.close()
