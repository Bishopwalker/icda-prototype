"""
Level 2: Index Validation - Periodic Health Checks.

Validates the entire index periodically for:
- Duplicates/near-duplicates
- Outdated content
- Coverage gaps
"""

import json
import re
import time
import logging
from datetime import datetime
from typing import Any

from .base import BaseLLMClient
from .models import (
    IndexHealthReport,
    DuplicateCluster,
    StaleContent,
    CoverageGap,
)

logger = logging.getLogger(__name__)


class IndexValidator:
    """
    Level 2 Enforcer: Validates index health periodically.

    Checks for:
    - Duplicate content (>80% similarity)
    - Stale content (outdated references)
    - Coverage gaps (missing topics)

    Generates a health report with recommendations.
    Works with any LLM provider.
    """

    SYSTEM_PROMPT = """You are an index health analyzer for a RAG knowledge system.
Analyze the provided index sample for quality issues.

Focus on:
1. DUPLICATES: Chunks that say essentially the same thing
2. STALENESS: Content with outdated info, deprecated APIs, old dates
3. COVERAGE: Missing important topics that should be indexed
4. CONSISTENCY: Contradictions between chunks

Be thorough but practical. Only flag real issues."""

    def __init__(self, client: BaseLLMClient, opensearch_client: Any = None):
        """
        Initialize the index validator.

        Args:
            client: Any LLM client implementing BaseLLMClient
            opensearch_client: Optional OpenSearch client for direct queries
        """
        self.client = client
        self.opensearch = opensearch_client
        self.stats = {
            "validations_run": 0,
            "duplicates_found": 0,
            "stale_found": 0,
            "gaps_found": 0,
        }

    async def validate_index(
        self,
        chunks: list[dict[str, Any]],
        sample_size: int = 100,
    ) -> IndexHealthReport:
        """
        Run full index validation.

        Args:
            chunks: List of chunk dicts with 'chunk_id', 'content', etc.
            sample_size: Number of chunks to sample for analysis

        Returns:
            IndexHealthReport with findings
        """
        start = time.time()

        # Sample chunks for analysis
        sample = self._sample_chunks(chunks, sample_size)

        # Run analysis phases
        duplicates = await self._find_duplicates(sample)
        stale = await self._find_stale_content(sample)
        gaps = await self._find_coverage_gaps(sample)

        # Calculate health score
        health_score = self._calculate_health_score(
            len(chunks),
            len(duplicates),
            len(stale),
            len(gaps),
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(duplicates, stale, gaps)

        # Update stats
        self.stats["validations_run"] += 1
        self.stats["duplicates_found"] += len(duplicates)
        self.stats["stale_found"] += len(stale)
        self.stats["gaps_found"] += len(gaps)

        return IndexHealthReport(
            timestamp=datetime.utcnow().isoformat(),
            total_chunks=len(chunks),
            unique_documents=len(set(c.get("doc_id") for c in chunks)),
            duplicate_clusters=duplicates,
            stale_content=stale,
            coverage_gaps=gaps,
            health_score=health_score,
            recommendations=recommendations,
            processing_time_ms=int((time.time() - start) * 1000),
        )

    def _sample_chunks(
        self,
        chunks: list[dict],
        sample_size: int,
    ) -> list[dict]:
        """Stratified sampling of chunks by category."""
        if len(chunks) <= sample_size:
            return chunks

        # Group by category
        by_category: dict[str, list] = {}
        for chunk in chunks:
            cat = chunk.get("category", "unknown")
            by_category.setdefault(cat, []).append(chunk)

        # Sample proportionally
        sample = []
        for cat, cat_chunks in by_category.items():
            proportion = len(cat_chunks) / len(chunks)
            n = max(1, int(sample_size * proportion))
            step = max(1, len(cat_chunks) // n)
            sample.extend(cat_chunks[::step][:n])

        return sample[:sample_size]

    async def _find_duplicates(
        self,
        chunks: list[dict],
    ) -> list[DuplicateCluster]:
        """Use LLM to identify duplicate clusters."""
        if not self.client.available or not chunks:
            return []

        # Build summaries for comparison
        summaries = []
        for chunk in chunks[:50]:  # Limit for context window
            summaries.append({
                "id": chunk.get("chunk_id"),
                "preview": chunk.get("content", "")[:200],
            })

        prompt = f"""Analyze these chunk previews for duplicates (>80% similar content):

{json.dumps(summaries, indent=2)}

Return JSON array of duplicate clusters:
[
    {{"primary_id": "...", "duplicate_ids": [...], "similarity": 0.9, "action": "merge"}}
]

Only return actual duplicates. Empty array if none found."""

        result = await self.client.generate(prompt, self.SYSTEM_PROMPT)

        if not result.success:
            return []

        try:
            match = re.search(r'\[[\s\S]*\]', result.text)
            if not match:
                return []
            data = json.loads(match.group())
            return [
                DuplicateCluster(
                    primary_id=d.get("primary_id", ""),
                    duplicate_ids=d.get("duplicate_ids", []),
                    similarity_score=d.get("similarity", 0.8),
                    recommendation=d.get("action", "review"),
                )
                for d in data if d.get("primary_id")
            ]
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse duplicates response: {e}")
            return []

    async def _find_stale_content(
        self,
        chunks: list[dict],
    ) -> list[StaleContent]:
        """Identify outdated content."""
        if not self.client.available:
            return []

        # Find chunks with potential staleness indicators
        samples = []
        stale_keywords = ["deprecated", "version", "2023", "2022", "2021", "legacy", "old"]

        for chunk in chunks[:30]:
            content = chunk.get("content", "").lower()
            if any(kw in content for kw in stale_keywords):
                samples.append({
                    "id": chunk.get("chunk_id"),
                    "preview": chunk.get("content", "")[:300],
                })

        if not samples:
            return []

        prompt = f"""Check these chunks for stale/outdated content:

{json.dumps(samples, indent=2)}

Return JSON array of stale items:
[
    {{"id": "...", "reason": "References deprecated API", "recommendation": "update"}}
]

Only flag genuinely outdated content. Empty array if none found."""

        result = await self.client.generate(prompt, self.SYSTEM_PROMPT)

        if not result.success:
            return []

        try:
            match = re.search(r'\[[\s\S]*\]', result.text)
            if not match:
                return []
            data = json.loads(match.group())
            return [
                StaleContent(
                    chunk_id=s.get("id", ""),
                    reason=s.get("reason", ""),
                    recommendation=s.get("recommendation", "review"),
                )
                for s in data if s.get("id")
            ]
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse stale content response: {e}")
            return []

    async def _find_coverage_gaps(
        self,
        chunks: list[dict],
    ) -> list[CoverageGap]:
        """Identify missing topics."""
        if not self.client.available:
            return []

        # Get topic distribution
        topics = set()
        for chunk in chunks:
            tags = chunk.get("tags", [])
            if isinstance(tags, list):
                topics.update(tags)

        prompt = f"""Given this RAG index covers these topics:
{list(topics)[:50]}

And contains {len(chunks)} chunks from a customer data query system.

What important topics might be MISSING? Consider:
- Common user questions
- Technical documentation gaps
- Integration/API coverage

Return JSON array:
[
    {{"topic": "...", "description": "...", "recommendation": "..."}}
]

Only suggest genuinely important gaps. Max 5 items."""

        result = await self.client.generate(prompt, self.SYSTEM_PROMPT)

        if not result.success:
            return []

        try:
            match = re.search(r'\[[\s\S]*\]', result.text)
            if not match:
                return []
            data = json.loads(match.group())
            return [
                CoverageGap(
                    topic=g.get("topic", ""),
                    description=g.get("description", ""),
                    recommendation=g.get("recommendation", "add content"),
                )
                for g in data[:5] if g.get("topic")
            ]
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"Failed to parse coverage gaps response: {e}")
            return []

    def _calculate_health_score(
        self,
        total: int,
        duplicates: int,
        stale: int,
        gaps: int,
    ) -> float:
        """Calculate overall health score (0-1)."""
        if total == 0:
            return 0.0

        # Penalties
        dup_penalty = min(0.3, (duplicates / max(total, 1)) * 3)
        stale_penalty = min(0.2, (stale / max(total, 1)) * 2)
        gap_penalty = min(0.2, gaps * 0.04)

        return max(0.0, 1.0 - dup_penalty - stale_penalty - gap_penalty)

    def _generate_recommendations(
        self,
        duplicates: list[DuplicateCluster],
        stale: list[StaleContent],
        gaps: list[CoverageGap],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recs = []

        if len(duplicates) > 5:
            recs.append(
                f"Merge or remove {len(duplicates)} duplicate clusters to reduce index noise"
            )

        if len(stale) > 3:
            recs.append(
                f"Update {len(stale)} stale chunks with current information"
            )

        if gaps:
            topics = [g.topic for g in gaps[:3]]
            recs.append(f"Add documentation for: {', '.join(topics)}")

        if not recs:
            recs.append("Index health is good - no major issues detected")

        return recs

    def get_stats(self) -> dict[str, Any]:
        """Get validator statistics."""
        return self.stats.copy()
