"""Intent Agent - Classifies query intent and determines domains.

This agent is the first in the pipeline. It analyzes the user's query to:
1. Classify the primary intent (LOOKUP, SEARCH, STATS, etc.)
2. Detect secondary intents
3. Determine relevant domains (customer, address, knowledge, etc.)
4. Assess query complexity
5. Suggest tools that might be useful
"""

import logging
import re
from typing import Any

from icda.classifier import QueryComplexity, QueryIntent

from .models import IntentResult, QueryDomain

logger = logging.getLogger(__name__)


class IntentAgent:
    """Classifies query intent and determines relevant domains.

    Uses pattern matching with fallback to semantic classification if available.
    Follows the enforcer pattern - receives only the context it needs.
    """
    __slots__ = ("_vector_index", "_available")

    # Pattern definitions for intent detection
    LOOKUP_PATTERNS = (
        r"\bcrid[-\s]?\d+",
        r"\bcustomer\s+id",
        r"\blook\s*up\b",
        r"\bfind\s+customer\b",
        r"\bget\s+customer\b",
        r"\bshow\s+me\s+customer\b",
        r"\bpull\s+up\b",
        r"\bcustomer\s+record\b",
        r"\bcustomer\s+details\b",
    )

    STATS_PATTERNS = (
        r"\bhow\s+many\b",
        r"\bcount\b",
        r"\bstatistics?\b",
        r"\btotals?\b",
        r"\bper\s+state\b",
        r"\bby\s+state\b",
        r"\bbreakdown\b",
        r"\bnumbers?\b",
        r"\bsummary\b",
        r"\baggregate\b",
    )

    SEARCH_PATTERNS = (
        r"\bsearch\b",
        r"\bfind\b",
        r"\bshow\b",
        r"\blist\b",
        r"\bgive\s+me\b",
        r"\bcustomers?\s+in\b",
        r"\bpeople\s+in\b",
        r"\bwho\s+lives?\b",
        r"\bresidents?\b",
        r"\bliving\s+in\b",
        r"\bfrom\b",
        r"\bmoved\b",
        r"\bmovers?\b",
        r"\brelocated\b",
        r"\bhigh\s+movers?\b",
        r"\bfrequent\b",
    )

    ANALYSIS_PATTERNS = (
        r"\btrend\b",
        r"\bpattern\b",
        r"\banalyze\b",
        r"\banalysis\b",
        r"\binsight\b",
        r"\bwhy\b",
        r"\bmigration\b",
        r"\bmovement\b",
        r"\bbehavior\b",
    )

    COMPARISON_PATTERNS = (
        r"\bcompare\b",
        r"\bvs\.?\b",
        r"\bversus\b",
        r"\bdifference\b",
        r"\bbetween\b",
        r"\bcomparison\b",
    )

    RECOMMENDATION_PATTERNS = (
        r"\brecommend\b",
        r"\bsuggest\b",
        r"\bshould\b",
        r"\bpredict\b",
        r"\bforecast\b",
        r"\bwhich\s+customers?\b",
    )

    ADDRESS_PATTERNS = (
        r"\baddress\b",
        r"\bverify\b",
        r"\bvalidate\b",
        r"\bnormalize\b",
        r"\bstreet\b",
        r"\bzip\s*code\b",
        r"\bpostal\b",
    )

    KNOWLEDGE_PATTERNS = (
        r"\bpolicy\b",
        r"\bprocedure\b",
        r"\bdocumentation\b",
        r"\bhow\s+do\s+i\b",
        r"\bwhat\s+is\s+the\s+process\b",
        r"\brules?\b",
        r"\bguidelines?\b",
    )

    # Complexity indicators
    COMPLEX_INDICATORS = (
        r"\btrend\b",
        r"\bpattern\b",
        r"\banalyze\b",
        r"\banalysis\b",
        r"\brecommend\b",
        r"\bpredict\b",
        r"\binsight\b",
        r"\bwhy\b",
        r"\bforecast\b",
        r"\bmigration\b",
        r"\bbehavior\b",
    )

    MEDIUM_INDICATORS = (
        r"\bcompare\b",
        r"\bfilter\b",
        r"\bbetween\b",
        r"\bsummary\b",
        r"\bper\s+state\b",
        r"\bwho\s+moved\b",
        r"\bwhich\b",
        r"\bmultiple\b",
        r"\bseveral\b",
        r"\ball\b",
        r"\bmost\b",
        r"\bleast\b",
        r"\btop\b",
        r"\bbottom\b",
    )

    def __init__(self, vector_index=None):
        """Initialize IntentAgent.

        Args:
            vector_index: Optional VectorIndex for semantic classification.
        """
        self._vector_index = vector_index
        self._available = True

    @property
    def available(self) -> bool:
        """Check if agent is available."""
        return self._available

    async def classify(self, query: str, session_id: str | None = None) -> IntentResult:
        """Classify query intent and determine domains.

        Args:
            query: The user's query text.
            session_id: Optional session ID for context.

        Returns:
            IntentResult with classification details.
        """
        q = query.lower().strip()
        signals: dict[str, Any] = {"patterns_matched": []}

        # Detect primary intent
        primary_intent, intent_confidence = self._detect_intent(q, signals)

        # Detect secondary intents
        secondary_intents = self._detect_secondary_intents(q, primary_intent)

        # Determine domains
        domains = self._detect_domains(q, primary_intent)

        # Assess complexity
        complexity = self._assess_complexity(q)

        # Suggest tools based on intent and domains
        suggested_tools = self._suggest_tools(primary_intent, domains, complexity)

        # Calculate overall confidence
        confidence = self._calculate_confidence(q, primary_intent, intent_confidence, signals)

        return IntentResult(
            primary_intent=primary_intent,
            secondary_intents=secondary_intents,
            confidence=confidence,
            domains=domains,
            complexity=complexity,
            suggested_tools=suggested_tools,
            raw_signals=signals,
        )

    def _detect_intent(self, query: str, signals: dict) -> tuple[QueryIntent, float]:
        """Detect primary query intent using pattern matching.

        Args:
            query: Lowercased query.
            signals: Dict to store debug info.

        Returns:
            Tuple of (intent, confidence).
        """
        # Check for LOOKUP first (highest priority if CRID present)
        if self._match_patterns(query, self.LOOKUP_PATTERNS):
            signals["patterns_matched"].append("lookup")
            # Extra confidence if actual CRID pattern found
            if re.search(r"crid[-\s]?\d+", query):
                return QueryIntent.LOOKUP, 0.95
            return QueryIntent.LOOKUP, 0.8

        # Check for STATS
        if self._match_patterns(query, self.STATS_PATTERNS):
            signals["patterns_matched"].append("stats")
            return QueryIntent.STATS, 0.85

        # Check for COMPARISON
        if self._match_patterns(query, self.COMPARISON_PATTERNS):
            signals["patterns_matched"].append("comparison")
            return QueryIntent.COMPARISON, 0.8

        # Check for ANALYSIS
        if self._match_patterns(query, self.ANALYSIS_PATTERNS):
            signals["patterns_matched"].append("analysis")
            return QueryIntent.ANALYSIS, 0.8

        # Check for RECOMMENDATION
        if self._match_patterns(query, self.RECOMMENDATION_PATTERNS):
            signals["patterns_matched"].append("recommendation")
            return QueryIntent.RECOMMENDATION, 0.75

        # Check for SEARCH (default for customer queries)
        if self._match_patterns(query, self.SEARCH_PATTERNS):
            signals["patterns_matched"].append("search")
            return QueryIntent.SEARCH, 0.85

        # Default to SEARCH for anything that looks customer-related
        signals["patterns_matched"].append("default_search")
        return QueryIntent.SEARCH, 0.6

    def _detect_secondary_intents(self, query: str, primary: QueryIntent) -> list[QueryIntent]:
        """Detect secondary intents that might also be relevant.

        Args:
            query: Lowercased query.
            primary: Primary detected intent.

        Returns:
            List of secondary intents.
        """
        secondary = []

        intent_patterns = [
            (QueryIntent.LOOKUP, self.LOOKUP_PATTERNS),
            (QueryIntent.STATS, self.STATS_PATTERNS),
            (QueryIntent.SEARCH, self.SEARCH_PATTERNS),
            (QueryIntent.ANALYSIS, self.ANALYSIS_PATTERNS),
            (QueryIntent.COMPARISON, self.COMPARISON_PATTERNS),
            (QueryIntent.RECOMMENDATION, self.RECOMMENDATION_PATTERNS),
        ]

        for intent, patterns in intent_patterns:
            if intent != primary and self._match_patterns(query, patterns):
                secondary.append(intent)

        return secondary[:2]  # Limit to top 2 secondary intents

    def _detect_domains(self, query: str, primary_intent: QueryIntent) -> list[QueryDomain]:
        """Detect relevant query domains.

        Args:
            query: Lowercased query.
            primary_intent: Primary detected intent.

        Returns:
            List of relevant domains.
        """
        domains = []

        # Always include CUSTOMER for most queries
        if primary_intent in (QueryIntent.LOOKUP, QueryIntent.SEARCH, QueryIntent.STATS):
            domains.append(QueryDomain.CUSTOMER)

        # Check for ADDRESS domain
        if self._match_patterns(query, self.ADDRESS_PATTERNS):
            domains.append(QueryDomain.ADDRESS)

        # Check for KNOWLEDGE domain
        if self._match_patterns(query, self.KNOWLEDGE_PATTERNS):
            domains.append(QueryDomain.KNOWLEDGE)

        # Check for STATS domain
        if primary_intent == QueryIntent.STATS or self._match_patterns(query, self.STATS_PATTERNS):
            if QueryDomain.STATS not in domains:
                domains.append(QueryDomain.STATS)

        # Default to CUSTOMER if nothing else matched
        if not domains:
            domains.append(QueryDomain.CUSTOMER)

        return domains

    def _assess_complexity(self, query: str) -> QueryComplexity:
        """Assess query complexity level.

        Args:
            query: Lowercased query.

        Returns:
            QueryComplexity level.
        """
        # Check for complex indicators
        if self._match_patterns(query, self.COMPLEX_INDICATORS):
            return QueryComplexity.COMPLEX

        # Check for medium indicators
        if self._match_patterns(query, self.MEDIUM_INDICATORS):
            return QueryComplexity.MEDIUM

        # Word count heuristic
        word_count = len(query.split())
        if word_count > 15:
            return QueryComplexity.COMPLEX
        if word_count > 8:
            return QueryComplexity.MEDIUM

        return QueryComplexity.SIMPLE

    def _suggest_tools(
        self,
        primary_intent: QueryIntent,
        domains: list[QueryDomain],
        complexity: QueryComplexity,
    ) -> list[str]:
        """Suggest tools based on intent, domains, and complexity.

        Args:
            primary_intent: Primary detected intent.
            domains: Relevant domains.
            complexity: Query complexity.

        Returns:
            List of suggested tool names.
        """
        tools = []

        # Intent-based suggestions
        match primary_intent:
            case QueryIntent.LOOKUP:
                tools.append("lookup_crid")
            case QueryIntent.SEARCH:
                tools.append("search_customers")
                if complexity != QueryComplexity.SIMPLE:
                    tools.append("fuzzy_search")
                    tools.append("semantic_search")
            case QueryIntent.STATS:
                tools.append("get_stats")
            case QueryIntent.ANALYSIS | QueryIntent.COMPARISON:
                tools.extend(["get_stats", "search_customers", "semantic_search"])
            case QueryIntent.RECOMMENDATION:
                tools.extend(["search_customers", "semantic_search", "get_stats"])

        # Domain-based additions
        if QueryDomain.ADDRESS in domains:
            tools.append("verify_address")
        if QueryDomain.KNOWLEDGE in domains:
            tools.append("search_knowledge")

        # Complexity-based additions
        if complexity == QueryComplexity.COMPLEX:
            if "hybrid_search" not in tools:
                tools.append("hybrid_search")

        return list(dict.fromkeys(tools))  # Remove duplicates while preserving order

    def _calculate_confidence(
        self,
        query: str,
        primary_intent: QueryIntent,
        intent_confidence: float,
        signals: dict,
    ) -> float:
        """Calculate overall classification confidence.

        Args:
            query: Original query.
            primary_intent: Detected intent.
            intent_confidence: Confidence from intent detection.
            signals: Debug signals dict.

        Returns:
            Overall confidence score (0.0 - 1.0).
        """
        confidence = intent_confidence

        # Boost confidence if multiple patterns matched
        if len(signals.get("patterns_matched", [])) > 1:
            confidence = min(confidence + 0.1, 1.0)

        # Reduce confidence for very short queries
        if len(query.split()) < 3:
            confidence *= 0.9

        # Reduce confidence for very long queries (might be complex)
        if len(query.split()) > 20:
            confidence *= 0.85

        return round(confidence, 3)

    def _match_patterns(self, text: str, patterns: tuple) -> bool:
        """Check if any pattern matches the text.

        Args:
            text: Text to search.
            patterns: Tuple of regex patterns.

        Returns:
            True if any pattern matches.
        """
        return any(re.search(p, text) for p in patterns)
