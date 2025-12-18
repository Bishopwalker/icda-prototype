"""Search Agent - Executes optimal search strategy.

This agent:
1. Selects the best search strategy based on resolved query
2. Executes searches with fallback on failure
3. Aggregates results from multiple strategies
4. Returns confidence-scored results
"""

import logging
from typing import Any

from .models import (
    IntentResult,
    ParsedQuery,
    ResolvedQuery,
    SearchResult,
    SearchStrategy,
)

logger = logging.getLogger(__name__)


class SearchAgent:
    """Executes search strategies and returns results.

    Follows the enforcer pattern - receives only the context it needs.
    """
    __slots__ = ("_db", "_vector_index", "_available")

    def __init__(self, db, vector_index=None):
        """Initialize SearchAgent.

        Args:
            db: CustomerDB for searches.
            vector_index: Optional VectorIndex for semantic search.
        """
        self._db = db
        self._vector_index = vector_index
        self._available = True

    @property
    def available(self) -> bool:
        """Check if agent is available."""
        return self._available

    async def search(
        self,
        resolved: ResolvedQuery,
        parsed: ParsedQuery,
        intent: IntentResult,
    ) -> SearchResult:
        """Execute search based on resolved query.

        Args:
            resolved: Resolved query from ResolverAgent.
            parsed: Parsed query from ParserAgent.
            intent: Intent classification.

        Returns:
            SearchResult with results and metadata.
        """
        # If we have resolved customers from direct lookup, return them
        if resolved.resolved_customers:
            return SearchResult(
                strategy_used=SearchStrategy.EXACT,
                results=resolved.resolved_customers,
                total_matches=len(resolved.resolved_customers),
                search_metadata={"source": "direct_lookup"},
                alternatives_tried=[],
                search_confidence=0.95,
            )

        # Try strategies in order of preference
        results = []
        alternatives_tried = []
        strategy_used = SearchStrategy.KEYWORD
        metadata = {}

        for strategy in resolved.fallback_strategies:
            try:
                strategy_results, strategy_meta = await self._execute_strategy(
                    strategy, parsed, resolved, intent
                )

                if strategy_results:
                    results = strategy_results
                    metadata = strategy_meta
                    strategy_used = self._map_strategy(strategy)
                    break
                else:
                    alternatives_tried.append(strategy)

            except Exception as e:
                logger.warning(f"Strategy {strategy} failed: {e}")
                alternatives_tried.append(f"{strategy}:failed")

        # Calculate confidence based on results and strategy
        confidence = self._calculate_confidence(
            results, strategy_used, alternatives_tried, parsed
        )

        return SearchResult(
            strategy_used=strategy_used,
            results=results[:parsed.limit],
            total_matches=len(results),
            search_metadata=metadata,
            alternatives_tried=alternatives_tried,
            search_confidence=confidence,
        )

    async def _execute_strategy(
        self,
        strategy: str,
        parsed: ParsedQuery,
        resolved: ResolvedQuery,
        intent: IntentResult,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Execute a specific search strategy.

        Args:
            strategy: Strategy name.
            parsed: Parsed query.
            resolved: Resolved query.
            intent: Intent classification.

        Returns:
            Tuple of (results, metadata).
        """
        metadata = {"strategy": strategy}

        match strategy:
            case "direct_lookup":
                return await self._direct_lookup(resolved)

            case "filtered_search":
                return await self._filtered_search(parsed)

            case "fuzzy_search":
                return await self._fuzzy_search(parsed)

            case "semantic_search":
                return await self._semantic_search(parsed, resolved)

            case "hybrid_search":
                return await self._hybrid_search(parsed, resolved)

            case "basic_search":
                return await self._basic_search(parsed)

            case _:
                logger.warning(f"Unknown strategy: {strategy}")
                return [], metadata

    async def _direct_lookup(
        self,
        resolved: ResolvedQuery,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Direct CRID lookup.

        Args:
            resolved: Resolved query with CRIDs.

        Returns:
            Tuple of (results, metadata).
        """
        results = []
        for crid in resolved.resolved_crids:
            try:
                result = self._db.lookup(crid)
                # Database returns "data" key, not "customer"
                if result.get("success") and result.get("data"):
                    results.append(result["data"])
            except Exception as e:
                logger.warning(f"Lookup failed for {crid}: {e}")

        return results, {"source": "direct_lookup", "crids": resolved.resolved_crids}

    async def _filtered_search(
        self,
        parsed: ParsedQuery,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Search with filters.

        Args:
            parsed: Parsed query with filters.

        Returns:
            Tuple of (results, metadata).
        """
        filters = parsed.filters
        result = self._db.search(
            state=filters.get("state"),
            city=filters.get("city"),
            min_moves=filters.get("min_move_count"),
            limit=parsed.limit * 2,  # Get extra for confidence
        )

        if result.get("success"):
            # Database returns "data" key, not "results"
            customers = result.get("data", [])
            return customers, {"filters_applied": filters, "total": result.get("total", 0)}

        return [], {"error": result.get("error")}

    async def _fuzzy_search(
        self,
        parsed: ParsedQuery,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fuzzy/typo-tolerant search.

        Args:
            parsed: Parsed query.

        Returns:
            Tuple of (results, metadata).
        """
        if not hasattr(self._db, "autocomplete_fuzzy"):
            return [], {"error": "Fuzzy search not available"}

        # Try to search on name or city
        results = []
        query_terms = parsed.normalized_query.split()

        # Try each term
        for term in query_terms[:3]:  # Limit terms
            if len(term) >= 3:
                try:
                    fuzzy_result = self._db.autocomplete_fuzzy("name", term, limit=10)
                    # Database returns "data" key, not "results"
                    if fuzzy_result.get("data"):
                        results.extend(fuzzy_result["data"])
                except Exception as e:
                    logger.warning(f"Fuzzy search failed for '{term}': {e}")

        # Deduplicate by CRID
        seen = set()
        unique_results = []
        for r in results:
            crid = r.get("crid")
            if crid and crid not in seen:
                seen.add(crid)
                unique_results.append(r)

        return unique_results, {"method": "fuzzy", "terms_searched": query_terms[:3]}

    async def _semantic_search(
        self,
        parsed: ParsedQuery,
        resolved: ResolvedQuery,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Semantic/vector search.

        Args:
            parsed: Parsed query.
            resolved: Resolved query.

        Returns:
            Tuple of (results, metadata).
        """
        if not self._vector_index or not getattr(self._vector_index, "available", False):
            return [], {"error": "Semantic search not available"}

        if not hasattr(self._vector_index, "search_customers_semantic"):
            return [], {"error": "Semantic customer search not implemented"}

        try:
            state_filter = parsed.filters.get("state")
            results = await self._vector_index.search_customers_semantic(
                parsed.normalized_query,
                limit=parsed.limit * 2,
                state_filter=state_filter,
            )

            if isinstance(results, list):
                return results, {"method": "semantic", "state_filter": state_filter}

            return [], {"error": "Invalid semantic search response"}

        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")
            return [], {"error": str(e)}

    async def _hybrid_search(
        self,
        parsed: ParsedQuery,
        resolved: ResolvedQuery,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Combined text + semantic search.

        Args:
            parsed: Parsed query.
            resolved: Resolved query.

        Returns:
            Tuple of (results, metadata).
        """
        if not self._vector_index or not getattr(self._vector_index, "available", False):
            return [], {"error": "Hybrid search not available"}

        if not hasattr(self._vector_index, "search_customers_hybrid"):
            return [], {"error": "Hybrid customer search not implemented"}

        try:
            state_filter = parsed.filters.get("state")
            results = await self._vector_index.search_customers_hybrid(
                parsed.normalized_query,
                limit=parsed.limit * 2,
                state_filter=state_filter,
            )

            if isinstance(results, list):
                return results, {"method": "hybrid", "state_filter": state_filter}

            return [], {"error": "Invalid hybrid search response"}

        except Exception as e:
            logger.warning(f"Hybrid search failed: {e}")
            return [], {"error": str(e)}

    async def _basic_search(
        self,
        parsed: ParsedQuery,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Basic search without specific filters.

        Args:
            parsed: Parsed query.

        Returns:
            Tuple of (results, metadata).
        """
        # Try to extract any useful filter from the query
        result = self._db.search(limit=parsed.limit * 2)

        if result.get("success"):
            # Database returns "data" key, not "results"
            return result.get("data", []), {"method": "basic", "no_filters": True, "total": result.get("total", 0)}

        return [], {"error": result.get("error")}

    def _map_strategy(self, strategy_name: str) -> SearchStrategy:
        """Map strategy name to SearchStrategy enum.

        Args:
            strategy_name: Strategy name string.

        Returns:
            SearchStrategy enum value.
        """
        mapping = {
            "direct_lookup": SearchStrategy.EXACT,
            "filtered_search": SearchStrategy.KEYWORD,
            "fuzzy_search": SearchStrategy.FUZZY,
            "semantic_search": SearchStrategy.SEMANTIC,
            "hybrid_search": SearchStrategy.HYBRID,
            "basic_search": SearchStrategy.KEYWORD,
        }
        return mapping.get(strategy_name, SearchStrategy.KEYWORD)

    def _calculate_confidence(
        self,
        results: list,
        strategy: SearchStrategy,
        alternatives_tried: list,
        parsed: ParsedQuery,
    ) -> float:
        """Calculate search confidence.

        Args:
            results: Search results.
            strategy: Strategy used.
            alternatives_tried: Strategies that failed.
            parsed: Parsed query.

        Returns:
            Confidence score (0.0 - 1.0).
        """
        if not results:
            return 0.1

        confidence = 0.5  # Base

        # Strategy-based confidence
        strategy_confidence = {
            SearchStrategy.EXACT: 0.95,
            SearchStrategy.HYBRID: 0.85,
            SearchStrategy.SEMANTIC: 0.8,
            SearchStrategy.FUZZY: 0.7,
            SearchStrategy.KEYWORD: 0.65,
        }
        confidence = strategy_confidence.get(strategy, 0.5)

        # Reduce if many alternatives tried
        if len(alternatives_tried) > 2:
            confidence -= 0.1

        # Reduce if results seem sparse
        if len(results) < 3 and parsed.limit >= 10:
            confidence -= 0.1

        return max(0.1, min(1.0, round(confidence, 3)))
