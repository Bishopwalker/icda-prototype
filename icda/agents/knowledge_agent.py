"""Knowledge Agent - RAG retrieval from knowledge base.

This agent:
1. Searches the knowledge base for relevant context
2. Retrieves documentation chunks
3. Provides RAG context for response generation
"""

import logging
from typing import Any

from .models import IntentResult, ParsedQuery, KnowledgeContext, QueryDomain

logger = logging.getLogger(__name__)


class KnowledgeAgent:
    """Retrieves knowledge base context for RAG.

    Follows the enforcer pattern - receives only the context it needs.
    """
    __slots__ = ("_knowledge", "_available")

    def __init__(self, knowledge=None):
        """Initialize KnowledgeAgent.

        Args:
            knowledge: KnowledgeManager for RAG retrieval.
        """
        self._knowledge = knowledge
        self._available = knowledge is not None and getattr(knowledge, "available", False)

    @property
    def available(self) -> bool:
        """Check if agent is available."""
        return self._available

    async def retrieve(
        self,
        query: str,
        intent: IntentResult,
        parsed: ParsedQuery,
    ) -> KnowledgeContext:
        """Retrieve relevant knowledge context.

        Args:
            query: User query.
            intent: Intent classification.
            parsed: Parsed query.

        Returns:
            KnowledgeContext with retrieved chunks.
        """
        # Always try to retrieve knowledge - let the search determine relevance
        # Skip only if knowledge base not available
        if not self._available:
            logger.debug("KnowledgeAgent: Knowledge base not available")
            return KnowledgeContext(
                relevant_chunks=[],
                total_chunks_found=0,
                categories_searched=[],
                tags_matched=[],
                rag_confidence=0.0,
            )

        # Determine categories to search
        categories = self._determine_categories(intent, parsed)
        logger.info(f"KnowledgeAgent: Searching categories {categories} for query: {query[:50]}...")

        # Search knowledge base
        chunks, total, tags = await self._search_knowledge(
            query, categories, limit=5
        )

        # Calculate RAG confidence
        confidence = self._calculate_confidence(chunks, intent)

        logger.info(f"KnowledgeAgent: Found {len(chunks)} chunks, confidence={confidence:.2f}")

        return KnowledgeContext(
            relevant_chunks=chunks,
            total_chunks_found=total,
            categories_searched=categories,
            tags_matched=tags,
            rag_confidence=confidence,
        )

    def _should_augment(self, intent: IntentResult) -> bool:
        """Determine if knowledge augmentation would be helpful.

        Args:
            intent: Intent classification.

        Returns:
            True if RAG would be helpful.
        """
        # Augment for complex analysis or recommendation queries
        from icda.classifier import QueryIntent, QueryComplexity

        if intent.complexity == QueryComplexity.COMPLEX:
            return True

        if intent.primary_intent in (QueryIntent.ANALYSIS, QueryIntent.RECOMMENDATION):
            return True

        return False

    def _determine_categories(
        self,
        intent: IntentResult,
        parsed: ParsedQuery,
    ) -> list[str]:
        """Determine knowledge categories to search.

        Args:
            intent: Intent classification.
            parsed: Parsed query.

        Returns:
            List of category names. Includes None to search ALL categories.
        """
        # Always search without category filter first (None = all categories)
        # This ensures we find relevant knowledge regardless of how it was categorized
        categories = [None]  # None means search all categories

        # Also add specific categories for intent-based filtering
        from icda.classifier import QueryIntent

        intent_categories = {
            QueryIntent.LOOKUP: ["customer_data", "procedures"],
            QueryIntent.SEARCH: ["customer_data", "search_help"],
            QueryIntent.STATS: ["reports", "analytics"],
            QueryIntent.ANALYSIS: ["analytics", "reports", "procedures"],
            QueryIntent.COMPARISON: ["analytics", "reports"],
            QueryIntent.RECOMMENDATION: ["best_practices", "procedures"],
        }

        if intent.primary_intent in intent_categories:
            categories.extend(intent_categories[intent.primary_intent])

        # Always include general category
        categories.append("general")

        return list(dict.fromkeys(categories))  # Remove duplicates

    async def _search_knowledge(
        self,
        query: str,
        categories: list[str],
        limit: int = 5,
    ) -> tuple[list[dict[str, Any]], int, list[str]]:
        """Search knowledge base.

        Args:
            query: Search query.
            categories: Categories to search.
            limit: Max results.

        Returns:
            Tuple of (chunks, total_found, matched_tags).
        """
        if not self._knowledge:
            return [], 0, []

        chunks = []
        total = 0
        all_tags = set()

        try:
            # Search each category
            for category in categories:
                result = await self._execute_search(query, category, limit)

                if result.get("success"):
                    # KnowledgeManager returns "hits" not "results"
                    hits = result.get("hits", result.get("results", []))
                    for chunk in hits:
                        chunks.append({
                            "text": chunk.get("text", ""),
                            "source": chunk.get("filename", chunk.get("source", "")),
                            "category": chunk.get("category", category),
                            "score": chunk.get("score", 0),
                        })
                        if chunk.get("tags"):
                            all_tags.update(chunk["tags"])

                    total += result.get("total", len(hits))

            # Sort by score and limit
            chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
            chunks = chunks[:limit]

        except Exception as e:
            logger.warning(f"Knowledge search failed: {e}")

        return chunks, total, list(all_tags)

    async def _execute_search(
        self,
        query: str,
        category: str | None,
        limit: int,
    ) -> dict[str, Any]:
        """Execute knowledge search.

        Args:
            query: Search query.
            category: Optional category filter.
            limit: Max results.

        Returns:
            Search result dict.
        """
        try:
            if hasattr(self._knowledge, "search"):
                # Check if search is async
                import asyncio
                result = self._knowledge.search(query, category=category, limit=limit)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            return {"success": False, "error": "No search method"}
        except Exception as e:
            logger.warning(f"Knowledge search error: {e}")
            return {"success": False, "error": str(e)}

    def _calculate_confidence(
        self,
        chunks: list[dict[str, Any]],
        intent: IntentResult,
    ) -> float:
        """Calculate RAG confidence.

        Args:
            chunks: Retrieved chunks.
            intent: Intent classification.

        Returns:
            Confidence score (0.0 - 1.0).
        """
        if not chunks:
            return 0.0

        # Base confidence from number of chunks
        confidence = 0.3 + (0.1 * min(len(chunks), 5))

        # Boost if scores are high
        avg_score = sum(c.get("score", 0) for c in chunks) / len(chunks)
        if avg_score > 0.8:
            confidence += 0.2
        elif avg_score > 0.5:
            confidence += 0.1

        # Boost if knowledge domain was specifically requested
        if QueryDomain.KNOWLEDGE in intent.domains:
            confidence += 0.15

        return min(1.0, round(confidence, 3))
