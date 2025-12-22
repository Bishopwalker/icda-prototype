"""
Level 3: Query Review - Runtime Quality Assurance.

Reviews queries and responses at runtime:
- Accuracy validation
- Hallucination detection
- Relevance scoring
- Feedback loop
"""

import json
import re
import time
import random
import logging
from typing import Any, Optional

from .base import BaseLLMClient
from .models import QueryReviewResult, QueryPattern

logger = logging.getLogger(__name__)


class QueryReviewer:
    """
    Level 3 Enforcer: Reviews queries and responses at runtime.

    Called after Nova generates a response to validate quality.
    Only reviews a sample of queries (based on sample_rate).
    Works with any LLM provider.
    """

    SYSTEM_PROMPT = """You are a response quality validator for a customer data assistant.
Your job is to verify that AI responses are:
1. ACCURATE: Response matches what's in the source chunks
2. GROUNDED: Response doesn't make up information not in sources
3. RELEVANT: The retrieved chunks actually answer the question

Be strict about hallucinations. Flag any claim not supported by sources."""

    REVIEW_PROMPT = """Review this query/response for quality:

QUERY: {query}

RETRIEVED CHUNKS:
{chunks}

AI RESPONSE: {response}

Analyze and return JSON:
{{
    "accuracy_score": <0.0-1.0>,
    "grounding_score": <0.0-1.0>,
    "relevance_score": <0.0-1.0>,
    "hallucination_detected": <true/false>,
    "hallucination_details": "<specifics if detected, null otherwise>",
    "chunk_relevance": {{"<chunk_id>": <0.0-1.0>, ...}},
    "feedback": ["<improvement suggestion>", ...]
}}"""

    def __init__(
        self,
        client: BaseLLMClient,
        sample_rate: float = 0.1,
    ):
        """
        Initialize the query reviewer.

        Args:
            client: Any LLM client implementing BaseLLMClient
            sample_rate: Fraction of queries to review (0.1 = 10%)
        """
        self.client = client
        self.sample_rate = sample_rate
        self.stats = {
            "queries_reviewed": 0,
            "hallucinations_detected": 0,
            "avg_accuracy": 0.0,
            "avg_grounding": 0.0,
            "avg_relevance": 0.0,
        }
        self.patterns: dict[str, QueryPattern] = {}

    def should_review(self) -> bool:
        """Determine if this query should be reviewed (sampling)."""
        return random.random() < self.sample_rate

    async def review_query(
        self,
        query_id: str,
        query_text: str,
        retrieved_chunks: list[dict[str, Any]],
        response_text: str,
    ) -> QueryReviewResult:
        """
        Review a query/response pair.

        Args:
            query_id: Unique query identifier
            query_text: The user's query
            retrieved_chunks: Chunks retrieved for context
            response_text: The AI-generated response

        Returns:
            QueryReviewResult with evaluation
        """
        start = time.time()

        # Default result for when client unavailable
        if not self.client.available:
            return self._default_result(query_id, query_text, start)

        # Format chunks for prompt
        chunks_text = "\n\n".join([
            f"[{c.get('chunk_id', 'unknown')}]: {c.get('text', c.get('content', ''))[:500]}"
            for c in retrieved_chunks[:5]
        ])

        prompt = self.REVIEW_PROMPT.format(
            query=query_text,
            chunks=chunks_text,
            response=response_text[:1000],
        )

        result = await self.client.generate(prompt, self.SYSTEM_PROMPT)

        if not result.success:
            logger.warning(f"Query review failed: {result.error}")
            return self._default_result(query_id, query_text, start)

        # Parse response
        try:
            match = re.search(r'\{[\s\S]*\}', result.text)
            if not match:
                raise ValueError("No JSON found")
            data = json.loads(match.group())
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse review response: {e}")
            return self._default_result(query_id, query_text, start)

        # Extract scores
        accuracy = float(data.get("accuracy_score", 0.7))
        grounding = float(data.get("grounding_score", 0.7))
        relevance = float(data.get("relevance_score", 0.7))

        overall = accuracy * 0.4 + grounding * 0.4 + relevance * 0.2

        hallucination = data.get("hallucination_detected", False)

        # Update stats
        self._update_stats(accuracy, grounding, relevance, hallucination)

        # Track patterns
        self._update_patterns(query_text, overall, data.get("feedback", []))

        return QueryReviewResult(
            query_id=query_id,
            query_text=query_text,
            accuracy_score=accuracy,
            grounding_score=grounding,
            relevance_score=relevance,
            overall_quality=overall,
            hallucination_detected=hallucination,
            hallucination_details=data.get("hallucination_details"),
            chunk_relevance=data.get("chunk_relevance", {}),
            feedback=data.get("feedback", []),
            processing_ms=int((time.time() - start) * 1000),
        )

    def _default_result(
        self,
        query_id: str,
        query_text: str,
        start: float,
    ) -> QueryReviewResult:
        """Return default result when review unavailable."""
        return QueryReviewResult(
            query_id=query_id,
            query_text=query_text,
            accuracy_score=0.7,
            grounding_score=0.7,
            relevance_score=0.7,
            overall_quality=0.7,
            hallucination_detected=False,
            feedback=["Review unavailable - manual check recommended"],
            processing_ms=int((time.time() - start) * 1000),
        )

    def _update_stats(
        self,
        accuracy: float,
        grounding: float,
        relevance: float,
        hallucination: bool,
    ) -> None:
        """Update running statistics."""
        self.stats["queries_reviewed"] += 1
        n = self.stats["queries_reviewed"]

        if hallucination:
            self.stats["hallucinations_detected"] += 1

        # Running averages
        self.stats["avg_accuracy"] = (
            (self.stats["avg_accuracy"] * (n - 1) + accuracy) / n
        )
        self.stats["avg_grounding"] = (
            (self.stats["avg_grounding"] * (n - 1) + grounding) / n
        )
        self.stats["avg_relevance"] = (
            (self.stats["avg_relevance"] * (n - 1) + relevance) / n
        )

    def _update_patterns(
        self,
        query: str,
        quality: float,
        issues: list[str],
    ) -> None:
        """Track query patterns for learning."""
        # Simple pattern extraction (first few words)
        words = query.lower().split()[:3]
        pattern = " ".join(words)

        if pattern not in self.patterns:
            self.patterns[pattern] = QueryPattern(pattern=pattern)

        p = self.patterns[pattern]
        p.frequency += 1
        p.avg_quality = ((p.avg_quality * (p.frequency - 1)) + quality) / p.frequency

        for issue in issues[:2]:
            if issue not in p.common_issues:
                p.common_issues.append(issue)
        p.common_issues = p.common_issues[:5]

    def get_problem_patterns(self, threshold: float = 0.6) -> list[QueryPattern]:
        """Get patterns with consistently low quality."""
        return [
            p for p in self.patterns.values()
            if p.frequency >= 3 and p.avg_quality < threshold
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get reviewer statistics."""
        return {
            **self.stats,
            "sample_rate": self.sample_rate,
            "hallucination_rate": (
                self.stats["hallucinations_detected"] / self.stats["queries_reviewed"]
                if self.stats["queries_reviewed"] > 0 else 0
            ),
            "problem_patterns": len(self.get_problem_patterns()),
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = {
            "queries_reviewed": 0,
            "hallucinations_detected": 0,
            "avg_accuracy": 0.0,
            "avg_grounding": 0.0,
            "avg_relevance": 0.0,
        }
        self.patterns.clear()
