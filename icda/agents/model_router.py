"""Model Router - Dynamic model selection based on query characteristics.

Routes queries to the appropriate Nova model (Micro/Lite/Pro) based on:
1. Query complexity classification
2. Agent confidence scores
3. Multi-part query detection
4. SQL complexity indicators

ROUTING DECISION TREE:
1. COMPLEX queries or analysis intents → Nova Pro
2. Low confidence from any agent → Nova Pro (needs reasoning power)
3. Multi-part queries → Nova Pro
4. SQL aggregation/analytics → Nova Pro
5. Large result sets (>100) → Nova Lite (good summarization)
6. MEDIUM complexity → Nova Lite
7. SIMPLE queries → Nova Micro (fast, cheap)
"""

import logging
from typing import Any

from icda.classifier import QueryComplexity, QueryIntent
from .models import (
    IntentResult,
    ParsedQuery,
    SearchResult,
    ModelTier,
    ModelRoutingDecision,
)

logger = logging.getLogger(__name__)


# SQL complexity indicators that require Nova Pro
SQL_COMPLEX_INDICATORS = frozenset([
    "aggregate", "aggregation", "join", "joined",
    "group by", "groupby", "having",
    "subquery", "nested", "union", "intersect", "except",
    "percentile", "median", "mode", "correlation",
    "average", "mean", "standard deviation", "variance",
    "trend", "pattern", "over time", "comparison",
    "breakdown", "distribution", "histogram",
])

# Intents that typically require more sophisticated reasoning
COMPLEX_INTENTS = frozenset([
    QueryIntent.ANALYSIS,
    QueryIntent.COMPARISON,
    QueryIntent.RECOMMENDATION,
])


class ModelRouter:
    """Routes queries to appropriate Nova model based on complexity.

    Decision hierarchy:
    1. COMPLEX complexity → Nova Pro
    2. Any agent confidence < threshold → Nova Pro
    3. Multi-part queries detected → Nova Pro
    4. SQL aggregation keywords → Nova Pro
    5. Large result sets (>100) → Nova Lite (better summarization)
    6. MEDIUM complexity → Nova Lite
    7. Otherwise → Nova Micro (fast path)
    """

    __slots__ = (
        "_micro_model",
        "_lite_model",
        "_pro_model",
        "_threshold",
    )

    def __init__(
        self,
        micro_model: str = "us.amazon.nova-micro-v1:0",
        lite_model: str = "us.amazon.nova-lite-v1:0",
        pro_model: str = "us.amazon.nova-pro-v1:0",
        confidence_threshold: float = 0.6,
    ):
        """Initialize ModelRouter.

        Args:
            micro_model: Model ID for simple queries.
            lite_model: Model ID for medium complexity queries.
            pro_model: Model ID for complex queries.
            confidence_threshold: Confidence below this triggers Pro model.
        """
        self._micro_model = micro_model
        self._lite_model = lite_model
        self._pro_model = pro_model
        self._threshold = confidence_threshold

        logger.info(
            f"ModelRouter initialized: micro={micro_model}, lite={lite_model}, "
            f"pro={pro_model}, threshold={confidence_threshold}"
        )

    def route(
        self,
        intent: IntentResult,
        parsed: ParsedQuery | None = None,
        search_result: SearchResult | None = None,
        agent_confidences: list[float] | None = None,
    ) -> ModelRoutingDecision:
        """Determine which model to use based on query characteristics.

        Args:
            intent: Intent classification result.
            parsed: Parsed query (optional).
            search_result: Search results (optional).
            agent_confidences: List of confidence scores from prior agents.

        Returns:
            ModelRoutingDecision with model selection and reasoning.
        """
        pro_reasons = []
        lite_reasons = []

        # =========================================================================
        # PRO-TIER CHECKS - These need maximum reasoning capability
        # =========================================================================

        # Rule 1: Complex query complexity
        if intent.complexity == QueryComplexity.COMPLEX:
            pro_reasons.append("complexity=COMPLEX")

        # Rule 2: Complex intent type (analysis, comparison, recommendation)
        if intent.primary_intent in COMPLEX_INTENTS:
            pro_reasons.append(f"intent={intent.primary_intent.value}")

        # Rule 3: Low intent confidence - uncertain = need Pro
        if intent.confidence < self._threshold:
            pro_reasons.append(f"intent_confidence={intent.confidence:.2f}")

        # Rule 4: Low confidence from any prior agent
        if agent_confidences:
            low_conf = [c for c in agent_confidences if c < self._threshold]
            if low_conf:
                min_conf = min(low_conf)
                pro_reasons.append(f"low_agent_confidence={min_conf:.2f}")

        # Rule 5: Multi-part query detection
        if parsed and self._is_multipart_query(parsed):
            pro_reasons.append("multipart_query")

        # Rule 6: SQL complexity indicators
        if self._has_sql_complexity(intent, parsed):
            pro_reasons.append("sql_complexity")

        # If any Pro reasons found, use Pro
        if pro_reasons:
            reason_str = "; ".join(pro_reasons)
            logger.info(f"ModelRouter: Nova Pro selected - {reason_str}")
            return ModelRoutingDecision(
                model_id=self._pro_model,
                model_tier=ModelTier.PRO,
                reason=reason_str,
                confidence_factor=intent.confidence,
            )

        # =========================================================================
        # LITE-TIER CHECKS - Medium complexity or special handling
        # =========================================================================

        # Rule 7: Large result sets need better summarization
        if search_result and search_result.total_matches > 100:
            reason = f"large_results={search_result.total_matches}"
            logger.info(f"ModelRouter: Nova Lite selected - {reason}")
            return ModelRoutingDecision(
                model_id=self._lite_model,
                model_tier=ModelTier.LITE,
                reason=reason,
                confidence_factor=intent.confidence,
            )

        # Rule 8: Medium complexity
        if intent.complexity == QueryComplexity.MEDIUM:
            reason = "complexity=MEDIUM"
            logger.info(f"ModelRouter: Nova Lite selected - {reason}")
            return ModelRoutingDecision(
                model_id=self._lite_model,
                model_tier=ModelTier.LITE,
                reason=reason,
                confidence_factor=intent.confidence,
            )

        # =========================================================================
        # MICRO-TIER - Simple, high-confidence queries (fast path)
        # =========================================================================

        reason = "complexity=SIMPLE"
        logger.info(f"ModelRouter: Nova Micro selected - {reason}")
        return ModelRoutingDecision(
            model_id=self._micro_model,
            model_tier=ModelTier.MICRO,
            reason=reason,
            confidence_factor=intent.confidence,
        )

    def _is_multipart_query(self, parsed: ParsedQuery) -> bool:
        """Detect multi-part queries (multiple questions or compound requests).

        Args:
            parsed: Parsed query.

        Returns:
            True if query appears to have multiple parts.
        """
        query = parsed.original_query.lower()

        # Check for multiple question marks
        if query.count("?") > 1:
            return True

        # Check for continuation patterns
        continuation_patterns = [
            "and then", "also", "additionally", "as well as",
            "furthermore", "in addition", "plus", "along with",
            "and also", "and what about", "what about",
        ]
        if any(pattern in query for pattern in continuation_patterns):
            return True

        # Check for numbered lists
        if any(f"{i}." in query or f"{i})" in query for i in range(1, 5)):
            return True

        return False

    def _has_sql_complexity(
        self,
        intent: IntentResult,
        parsed: ParsedQuery | None,
    ) -> bool:
        """Check if query requires complex SQL-like reasoning.

        Args:
            intent: Intent result.
            parsed: Parsed query.

        Returns:
            True if complex aggregation/analysis detected.
        """
        # Check original query from intent signals
        query_text = intent.raw_signals.get("original_query", "")
        if parsed:
            query_text = f"{query_text} {parsed.normalized_query}"

        query_lower = query_text.lower()

        # Check for SQL complexity indicators
        for indicator in SQL_COMPLEX_INDICATORS:
            if indicator in query_lower:
                return True

        return False

    @property
    def threshold(self) -> float:
        """Get the confidence threshold."""
        return self._threshold

    def get_model_for_tier(self, tier: ModelTier) -> str:
        """Get model ID for a specific tier.

        Args:
            tier: Model tier.

        Returns:
            Model ID string.
        """
        if tier == ModelTier.PRO:
            return self._pro_model
        elif tier == ModelTier.LITE:
            return self._lite_model
        elif tier == ModelTier.MICRO:
            return self._micro_model
        else:
            return self._micro_model  # Fallback to micro
