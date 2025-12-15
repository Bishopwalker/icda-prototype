"""EnforcerOrchestrator - Orchestrates the 5-Agent Pipeline.

Coordinates all 5 enforcer agents in sequence, manages batch processing,
and provides unified interface for knowledge indexing.

Pipeline Flow:
    Input → IntakeGuard → SemanticMiner → ContextLinker → QualityEnforcer → IndexSync → Output
"""

import asyncio
import logging
import time
from typing import Any

from .models import (
    BatchKnowledgeItem,
    BatchKnowledgeResult,
    BatchSummary,
    EnforcerResult,
)
from .quality_gates import (
    EnforcerGateResult,
    is_blocking_gate,
    summarize_gate_results,
)
from .agents import (
    IntakeGuardAgent,
    SemanticMinerAgent,
    ContextLinkerAgent,
    QualityEnforcerAgent,
    IndexSyncAgent,
)


logger = logging.getLogger(__name__)


class EnforcerOrchestrator:
    """Orchestrates the 5-agent enforcer pipeline.

    Coordinates:
    1. IntakeGuardAgent - Input validation
    2. SemanticMinerAgent - Entity/pattern extraction
    3. ContextLinkerAgent - Knowledge linking
    4. QualityEnforcerAgent - Quality validation
    5. IndexSyncAgent - OpenSearch indexing
    """

    def __init__(
        self,
        opensearch_client: Any = None,
        embedding_client: Any = None,
        index_name: str = "icda-knowledge",
    ):
        """Initialize the orchestrator.

        Args:
            opensearch_client: OpenSearch client for storage.
            embedding_client: Bedrock client for embeddings.
            index_name: Name of the knowledge index.
        """
        self.opensearch_client = opensearch_client
        self.embedding_client = embedding_client
        self.index_name = index_name

        # Initialize agents
        self.intake_agent = IntakeGuardAgent()
        self.semantic_agent = SemanticMinerAgent()
        self.context_agent = ContextLinkerAgent(opensearch_client)
        self.quality_agent = QualityEnforcerAgent()
        self.index_agent = IndexSyncAgent(
            opensearch_client,
            embedding_client,
            index_name,
        )

        self.stats = {
            "total_processed": 0,
            "total_successful": 0,
            "total_failed": 0,
            "batch_processed": 0,
            "pr_content_processed": 0,
        }

    async def process(
        self,
        content: str,
        filename: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EnforcerResult:
        """Process single content through the 5-agent pipeline.

        Args:
            content: Content to process.
            filename: Optional filename for format detection.
            metadata: Additional metadata.

        Returns:
            EnforcerResult with all agent results.
        """
        start_time = time.time()
        self.stats["total_processed"] += 1

        all_gates: list[EnforcerGateResult] = []
        agent_timings: dict[str, int] = {}

        result = EnforcerResult()

        try:
            # Agent 1: IntakeGuard
            agent_start = time.time()
            intake_result, intake_gates = await self.intake_agent.process(
                content, filename, metadata
            )
            agent_timings["intake"] = int((time.time() - agent_start) * 1000)
            all_gates.extend(intake_gates)
            result.intake = intake_result

            # Check for blocking failures
            if self._has_blocking_failure(intake_gates):
                logger.warning("Intake failed with blocking error")
                return self._finalize_result(result, all_gates, agent_timings, start_time, False)

            if intake_result.is_pr_relevant:
                self.stats["pr_content_processed"] += 1

            # Agent 2: SemanticMiner
            agent_start = time.time()
            semantic_result, semantic_gates = await self.semantic_agent.process(intake_result)
            agent_timings["semantic"] = int((time.time() - agent_start) * 1000)
            all_gates.extend(semantic_gates)
            result.semantic = semantic_result

            # Agent 3: ContextLinker
            agent_start = time.time()
            context_result, context_gates = await self.context_agent.process(
                semantic_result,
                content,
                intake_result.metadata.get("content_hash"),
            )
            agent_timings["context"] = int((time.time() - agent_start) * 1000)
            all_gates.extend(context_gates)
            result.context = context_result

            # Agent 4: QualityEnforcer
            agent_start = time.time()
            quality_result, quality_gates = await self.quality_agent.process(
                semantic_result,
                context_result,
                content,
            )
            agent_timings["quality"] = int((time.time() - agent_start) * 1000)
            all_gates.extend(quality_gates)
            result.quality = quality_result

            # Check quality threshold before indexing
            if self._has_blocking_failure(quality_gates):
                logger.warning("Quality validation failed with blocking error")
                return self._finalize_result(result, all_gates, agent_timings, start_time, False)

            # Agent 5: IndexSync
            agent_start = time.time()
            index_result, index_gates = await self.index_agent.process(
                content,
                semantic_result,
                quality_result,
                {
                    "content_type": intake_result.content_type.value,
                    "filename": filename,
                    **(metadata or {}),
                },
            )
            agent_timings["index"] = int((time.time() - agent_start) * 1000)
            all_gates.extend(index_gates)
            result.index = index_result

            # Mark content hash as known to prevent duplicates
            if index_result.success:
                content_hash = intake_result.metadata.get("content_hash")
                if content_hash:
                    self.intake_agent.add_known_hash(content_hash)

            success = index_result.success
            return self._finalize_result(result, all_gates, agent_timings, start_time, success)

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            self.stats["total_failed"] += 1
            result.success = False
            result.total_time_ms = int((time.time() - start_time) * 1000)
            result.agent_timings = agent_timings
            result.gates_failed = [g.gate.value for g in all_gates if not g.passed]
            return result

    async def process_batch(
        self,
        items: list[BatchKnowledgeItem],
        parallel_limit: int = 5,
        progress_callback: Any = None,
    ) -> tuple[list[BatchKnowledgeResult], BatchSummary]:
        """Process multiple items through the pipeline.

        Args:
            items: List of items to process.
            parallel_limit: Maximum concurrent processing.
            progress_callback: Optional callback(current, total).

        Returns:
            Tuple of (results list, summary statistics).
        """
        start_time = time.time()
        self.stats["batch_processed"] += 1

        results: list[BatchKnowledgeResult] = []
        semaphore = asyncio.Semaphore(parallel_limit)

        async def process_item(item: BatchKnowledgeItem, index: int) -> BatchKnowledgeResult:
            async with semaphore:
                item_start = time.time()

                enforcer_result = await self.process(
                    content=item.content,
                    metadata={
                        "content_type": item.content_type,
                        "batch_id": item.id,
                        **item.context,
                    },
                )

                item_time = int((time.time() - item_start) * 1000)

                # Determine stage reached
                stage = "index" if enforcer_result.index else \
                        "quality" if enforcer_result.quality else \
                        "context" if enforcer_result.context else \
                        "semantic" if enforcer_result.semantic else \
                        "intake"

                result = BatchKnowledgeResult(
                    id=item.id,
                    result=enforcer_result,
                    processing_time_ms=item_time,
                    stage_reached=stage,
                )

                if progress_callback:
                    progress_callback(index + 1, len(items))

                return result

        # Process all items with concurrency limit
        tasks = [process_item(item, i) for i, item in enumerate(items)]
        results = await asyncio.gather(*tasks)

        # Build summary
        total_time = int((time.time() - start_time) * 1000)
        summary = self._build_batch_summary(results, total_time)

        return results, summary

    def _has_blocking_failure(self, gates: list[EnforcerGateResult]) -> bool:
        """Check if any blocking gates failed.

        Args:
            gates: List of gate results.

        Returns:
            True if any blocking gate failed.
        """
        for gate in gates:
            if not gate.passed and is_blocking_gate(gate.gate):
                return True
        return False

    def _finalize_result(
        self,
        result: EnforcerResult,
        all_gates: list[EnforcerGateResult],
        agent_timings: dict[str, int],
        start_time: float,
        success: bool,
    ) -> EnforcerResult:
        """Finalize the enforcer result.

        Args:
            result: Partial result to finalize.
            all_gates: All gate results.
            agent_timings: Per-agent timing.
            start_time: Pipeline start time.
            success: Whether pipeline succeeded.

        Returns:
            Finalized EnforcerResult.
        """
        result.success = success
        result.gates_passed = [g.gate.value for g in all_gates if g.passed]
        result.gates_failed = [g.gate.value for g in all_gates if not g.passed]
        result.total_time_ms = int((time.time() - start_time) * 1000)
        result.agent_timings = agent_timings

        if success:
            self.stats["total_successful"] += 1
        else:
            self.stats["total_failed"] += 1

        return result

    def _build_batch_summary(
        self,
        results: list[BatchKnowledgeResult],
        total_time_ms: int,
    ) -> BatchSummary:
        """Build summary statistics for batch.

        Args:
            results: List of batch results.
            total_time_ms: Total batch processing time.

        Returns:
            BatchSummary with statistics.
        """
        successful = sum(1 for r in results if r.result.success)
        failed = len(results) - successful
        pr_items = sum(
            1 for r in results
            if r.result.intake and r.result.intake.is_pr_relevant
        )

        quality_scores = [
            r.result.quality.overall_score
            for r in results
            if r.result.quality
        ]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

        total_chunks = sum(
            r.result.index.chunks_created
            for r in results
            if r.result.index
        )

        return BatchSummary(
            total=len(results),
            successful=successful,
            failed=failed,
            avg_quality_score=avg_quality,
            total_chunks_created=total_chunks,
            total_time_ms=total_time_ms,
            pr_items=pr_items,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get orchestrator statistics.

        Returns:
            Combined statistics from orchestrator and all agents.
        """
        return {
            "orchestrator": self.stats.copy(),
            "intake_agent": self.intake_agent.get_stats(),
            "semantic_agent": self.semantic_agent.get_stats(),
            "context_agent": self.context_agent.get_stats(),
            "quality_agent": self.quality_agent.get_stats(),
            "index_agent": self.index_agent.get_stats(),
        }

    def set_clients(
        self,
        opensearch_client: Any = None,
        embedding_client: Any = None,
    ) -> None:
        """Set the OpenSearch and embedding clients.

        Args:
            opensearch_client: OpenSearch client.
            embedding_client: Bedrock embedding client.
        """
        if opensearch_client:
            self.opensearch_client = opensearch_client
            self.context_agent.set_opensearch_client(opensearch_client)
            self.index_agent.set_clients(opensearch_client=opensearch_client)

        if embedding_client:
            self.embedding_client = embedding_client
            self.index_agent.set_clients(embedding_client=embedding_client)
