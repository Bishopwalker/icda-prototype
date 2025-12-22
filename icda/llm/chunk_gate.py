"""
Level 1: Chunk Quality Gate - Pre-Index Validation.

Evaluates chunk quality before indexing using any LLM provider.
Checks coherence, completeness, and relevance.
"""

import json
import re
import time
import asyncio
import logging
from typing import Any

from .base import BaseLLMClient
from .models import ChunkQualityScore, ChunkGateResult

logger = logging.getLogger(__name__)


class ChunkQualityGate:
    """
    Level 1 Enforcer: Validates chunk quality before indexing.

    Uses any LLM provider to assess each chunk for:
    - Coherence (0.3 weight): Does it make sense standalone?
    - Completeness (0.4 weight): Is it a complete thought/code block?
    - Relevance (0.3 weight): Is it useful for RAG retrieval?

    Threshold: 0.6 overall score to pass by default.
    """

    SYSTEM_PROMPT = """You are a strict quality enforcer for a RAG knowledge index.
Your job is to evaluate chunks of text/code for indexing quality.

Score each dimension from 0.0 to 1.0:
- COHERENCE: Does this chunk make sense on its own? Is it readable?
- COMPLETENESS: Is this a complete thought, code block, or concept? Not truncated mid-sentence?
- RELEVANCE: Would this be useful when retrieved for a user query? Does it contain actionable info?

Be strict. Only approve chunks that would genuinely help answer questions.
Reject fragments, gibberish, and low-value content.
For borderline chunks, suggest specific improvements."""

    EVAL_PROMPT = """Evaluate this chunk for RAG indexing:

```
{content}
```

Source: {source}
Type: {content_type}

Respond with JSON only:
{{
    "coherence": <0.0-1.0>,
    "completeness": <0.0-1.0>,
    "relevance": <0.0-1.0>,
    "approved": <true/false>,
    "rejection_reason": "<reason if rejected, null otherwise>",
    "improvements": ["<suggestion1>", "<suggestion2>"]
}}"""

    def __init__(
        self,
        client: BaseLLMClient,
        threshold: float = 0.6,
        batch_size: int = 10,
    ):
        """
        Initialize the chunk quality gate.

        Args:
            client: Any LLM client implementing BaseLLMClient
            threshold: Minimum overall score to approve (0-1)
            batch_size: Chunks per batch for rate limiting
        """
        self.client = client
        self.threshold = threshold
        self.batch_size = batch_size
        self.stats = {
            "total_processed": 0,
            "approved": 0,
            "rejected": 0,
            "improved": 0,
            "rejection_reasons": {},
        }

    async def evaluate_chunk(
        self,
        chunk_id: str,
        content: str,
        source: str = "unknown",
        content_type: str = "text",
    ) -> ChunkQualityScore:
        """
        Evaluate a single chunk.

        Args:
            chunk_id: Unique chunk identifier
            content: Chunk text content
            source: Source filename or identifier
            content_type: Type of content (text, code, etc.)

        Returns:
            ChunkQualityScore with evaluation results
        """
        start = time.time()

        # Skip if client not available
        if not self.client.available:
            return self._default_score(chunk_id, start)

        # Build prompt
        prompt = self.EVAL_PROMPT.format(
            content=content[:2000],  # Truncate for efficiency
            source=source,
            content_type=content_type,
        )

        result = await self.client.generate(prompt, self.SYSTEM_PROMPT)

        if not result.success:
            logger.warning(f"Chunk evaluation failed: {result.error}")
            return self._default_score(chunk_id, start)

        # Parse JSON response
        try:
            json_match = re.search(r'\{[\s\S]*\}', result.text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return self._default_score(chunk_id, start)

        # Extract scores
        coherence = float(data.get("coherence", 0.5))
        completeness = float(data.get("completeness", 0.5))
        relevance = float(data.get("relevance", 0.5))

        # Calculate weighted overall score
        overall = (
            coherence * 0.3 +
            completeness * 0.4 +
            relevance * 0.3
        )

        approved = overall >= self.threshold

        # Update stats
        self.stats["total_processed"] += 1
        if approved:
            self.stats["approved"] += 1
        else:
            self.stats["rejected"] += 1
            reason = data.get("rejection_reason", "Below threshold")
            self.stats["rejection_reasons"][reason] = \
                self.stats["rejection_reasons"].get(reason, 0) + 1

        if data.get("improvements"):
            self.stats["improved"] += 1

        return ChunkQualityScore(
            chunk_id=chunk_id,
            coherence=coherence,
            completeness=completeness,
            relevance=relevance,
            overall=overall,
            approved=approved,
            rejection_reason=data.get("rejection_reason"),
            improvements=data.get("improvements", []),
            processing_ms=int((time.time() - start) * 1000),
        )

    def _default_score(self, chunk_id: str, start: float) -> ChunkQualityScore:
        """Return default passing score when evaluation unavailable."""
        return ChunkQualityScore(
            chunk_id=chunk_id,
            coherence=0.7,
            completeness=0.7,
            relevance=0.7,
            overall=0.7,
            approved=True,
            processing_ms=int((time.time() - start) * 1000),
        )

    async def evaluate_batch(
        self,
        chunks: list[dict[str, Any]],
    ) -> ChunkGateResult:
        """
        Evaluate a batch of chunks.

        Args:
            chunks: List of chunk dicts with 'chunk_id', 'content', 'source', 'content_type'

        Returns:
            ChunkGateResult with all evaluations
        """
        start = time.time()
        scores: list[ChunkQualityScore] = []

        # Process in batches to respect rate limits
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]

            tasks = [
                self.evaluate_chunk(
                    chunk.get("chunk_id", f"chunk_{i+j}"),
                    chunk.get("content", ""),
                    chunk.get("source", "unknown"),
                    chunk.get("content_type", "text"),
                )
                for j, chunk in enumerate(batch)
            ]

            batch_results = await asyncio.gather(*tasks)
            scores.extend(batch_results)

            # Small delay between batches
            if i + self.batch_size < len(chunks):
                await asyncio.sleep(0.5)

        # Calculate aggregates
        approved = sum(1 for s in scores if s.approved)
        rejected = len(scores) - approved
        improved = sum(1 for s in scores if s.improvements)

        avg_coherence = sum(s.coherence for s in scores) / len(scores) if scores else 0
        avg_completeness = sum(s.completeness for s in scores) / len(scores) if scores else 0
        avg_relevance = sum(s.relevance for s in scores) / len(scores) if scores else 0

        return ChunkGateResult(
            total_processed=len(scores),
            approved=approved,
            rejected=rejected,
            improved=improved,
            scores=scores,
            avg_coherence=avg_coherence,
            avg_completeness=avg_completeness,
            avg_relevance=avg_relevance,
            processing_time_ms=int((time.time() - start) * 1000),
        )

    def get_stats(self) -> dict[str, Any]:
        """Get gate statistics."""
        return {
            **self.stats,
            "threshold": self.threshold,
            "approval_rate": (
                self.stats["approved"] / self.stats["total_processed"]
                if self.stats["total_processed"] > 0 else 0
            ),
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = {
            "total_processed": 0,
            "approved": 0,
            "rejected": 0,
            "improved": 0,
            "rejection_reasons": {},
        }
