"""
Index Federation - Federated Search Across Multiple Indexes.

Provides unified search interface across the index hierarchy
with smart routing and result deduplication.

Features:
- Query routing based on master index hints
- Parallel search across domain indexes
- Result merging and deduplication
- Weighted scoring by index
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import asyncio
import logging

from .base_index import SearchResult
from .master_index import MasterIndex
from .code_index import CodeIndex
from .knowledge_index import KnowledgeIndex
from .customers_index import CustomersIndex
from .deduplication import DeduplicationManager

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FederatedResult:
    """A federated search result with source attribution."""
    doc_id: str
    chunk_id: str
    text: str
    score: float
    source_index: str
    is_deduplicated: bool = False
    alternate_sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FederatedSearchResponse:
    """Response from federated search."""
    results: list[FederatedResult]
    total_hits: int
    searched_indexes: list[str]
    routing_scores: dict[str, float]
    deduplicated_count: int
    processing_time_ms: int


class IndexFederation:
    """
    Federated search coordinator for the index hierarchy.

    Coordinates searches across:
    - MasterIndex: For routing decisions
    - CodeIndex: Development context
    - KnowledgeIndex: User documentation
    - CustomersIndex: Customer data

    Routing Strategy:
    1. Query hits master index for routing hints
    2. Based on scores, select 1-3 domain indexes
    3. Execute parallel searches
    4. Merge and deduplicate results
    5. Return ranked results with source attribution
    """

    # Index weights for scoring
    INDEX_WEIGHTS = {
        "code": 1.0,
        "knowledge": 1.2,  # Slightly prefer knowledge for general queries
        "customers": 1.0,
    }

    # Routing thresholds
    MIN_ROUTING_SCORE = 0.3
    MAX_INDEXES_TO_SEARCH = 3

    def __init__(
        self,
        opensearch_client: Any,
        embedder: Any,
        config: Optional[dict[str, str]] = None,
    ):
        """
        Initialize the federation.

        Args:
            opensearch_client: OpenSearch async client
            embedder: Embedding client
            config: Optional index name overrides
        """
        config = config or {}

        # Initialize master index
        self.master = MasterIndex(
            opensearch_client,
            embedder,
            index_name=config.get("master", "icda-master"),
        )

        # Initialize domain indexes
        self.code = CodeIndex(
            opensearch_client,
            embedder,
            index_name=config.get("code", "icda-code"),
        )

        self.knowledge = KnowledgeIndex(
            opensearch_client,
            embedder,
            index_name=config.get("knowledge", "icda-knowledge"),
        )

        self.customers = CustomersIndex(
            opensearch_client,
            embedder,
            index_name=config.get("customers", "icda-customers"),
        )

        # Map names to indexes
        self._indexes = {
            "code": self.code,
            "knowledge": self.knowledge,
            "customers": self.customers,
        }

        # Deduplication manager
        self.dedup = DeduplicationManager()

        self.embedder = embedder

    async def ensure_all_indexes(self) -> dict[str, bool]:
        """
        Ensure all indexes exist.

        Returns:
            Dict mapping index name to creation success
        """
        results = {}

        results["master"] = await self.master.ensure_index()
        results["code"] = await self.code.ensure_index()
        results["knowledge"] = await self.knowledge.ensure_index()
        results["customers"] = await self.customers.ensure_index()

        return results

    async def search(
        self,
        query: str,
        indexes: Optional[list[str]] = None,
        k: int = 10,
        deduplicate: bool = True,
        access_levels: Optional[list[str]] = None,
    ) -> FederatedSearchResponse:
        """
        Execute a federated search across indexes.

        Args:
            query: Search query
            indexes: Specific indexes to search (None = auto-route)
            k: Results per index
            deduplicate: Whether to deduplicate results
            access_levels: Filter by access levels

        Returns:
            FederatedSearchResponse with merged results
        """
        import time
        start = time.time()

        # Determine which indexes to search
        if indexes:
            # User specified indexes
            target_indexes = indexes
            routing_scores = {idx: 1.0 for idx in indexes}
        else:
            # Auto-route using master index
            routing = await self.master.route_query(
                query,
                k=self.MAX_INDEXES_TO_SEARCH,
                access_levels=access_levels,
            )

            # Filter by minimum score
            routing_scores = {
                idx: score
                for idx, score in routing
                if score >= self.MIN_ROUTING_SCORE
            }

            # Ensure at least one index
            if not routing_scores:
                routing_scores = {"knowledge": 0.5}

            target_indexes = list(routing_scores.keys())

        # Execute parallel searches
        search_tasks = []
        for idx_name in target_indexes:
            if idx_name in self._indexes:
                task = self._search_index(idx_name, query, k)
                search_tasks.append(task)

        results_by_index = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Merge results
        all_results: list[FederatedResult] = []

        for idx_name, results in zip(target_indexes, results_by_index):
            if isinstance(results, Exception):
                logger.error(f"Search failed for {idx_name}: {results}")
                continue

            weight = self.INDEX_WEIGHTS.get(idx_name, 1.0)
            routing_weight = routing_scores.get(idx_name, 1.0)

            for result in results:
                all_results.append(FederatedResult(
                    doc_id=result.doc_id,
                    chunk_id=result.chunk_id,
                    text=result.text,
                    score=result.score * weight * routing_weight,
                    source_index=idx_name,
                    metadata=result.metadata,
                ))

        # Deduplicate
        deduplicated_count = 0
        if deduplicate and len(all_results) > 0:
            all_results, deduplicated_count = self.dedup.deduplicate_results(all_results)

        # Sort by score
        all_results.sort(key=lambda r: r.score, reverse=True)

        # Limit total results
        all_results = all_results[:k * 2]  # Allow some extra for variety

        processing_time = int((time.time() - start) * 1000)

        return FederatedSearchResponse(
            results=all_results,
            total_hits=len(all_results),
            searched_indexes=target_indexes,
            routing_scores=routing_scores,
            deduplicated_count=deduplicated_count,
            processing_time_ms=processing_time,
        )

    async def _search_index(
        self,
        index_name: str,
        query: str,
        k: int,
    ) -> list[SearchResult]:
        """Execute search on a specific index."""
        index = self._indexes.get(index_name)
        if not index:
            return []

        # Generate embedding
        embedding = await index.generate_embedding(query)

        if embedding:
            return await index.knn_search(embedding=embedding, k=k)
        else:
            # Fallback to text search
            return await index.search(
                {"match": {"text": query}},
                size=k,
            )

    async def search_code(
        self,
        query: str,
        language: Optional[str] = None,
        k: int = 10,
    ) -> list[SearchResult]:
        """
        Search only the code index.

        Args:
            query: Search query
            language: Filter by language
            k: Number of results

        Returns:
            List of code search results
        """
        return await self.code.search_code(query, language=language, k=k)

    async def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        k: int = 10,
    ) -> list[SearchResult]:
        """
        Search only the knowledge index.

        Args:
            query: Search query
            category: Filter by category
            tags: Filter by tags
            k: Number of results

        Returns:
            List of knowledge search results
        """
        return await self.knowledge.search_knowledge(
            query,
            category=category,
            tags=tags,
            k=k,
        )

    async def search_customers(
        self,
        query: str,
        state: Optional[str] = None,
        k: int = 10,
    ) -> list[SearchResult]:
        """
        Search only the customers index.

        Args:
            query: Search query
            state: Filter by state
            k: Number of results

        Returns:
            List of customer search results
        """
        return await self.customers.search_customers(query, state=state, k=k)

    async def lookup_crid(self, crid: str) -> Optional[dict[str, Any]]:
        """Direct CRID lookup (bypasses federation)."""
        return await self.customers.lookup_crid(crid)

    async def get_all_stats(self) -> dict[str, Any]:
        """
        Get statistics from all indexes.

        Returns:
            Dict with stats per index
        """
        stats = {}

        stats["master"] = await self.master.get_stats()
        stats["code"] = await self.code.get_stats()
        stats["knowledge"] = await self.knowledge.get_stats()
        stats["customers"] = await self.customers.get_stats()

        # Distribution from master
        stats["distribution"] = await self.master.get_index_distribution()

        return stats

    async def sync_to_master(
        self,
        doc_id: str,
        source_index: str,
        title: str,
        summary: str,
        chunk_count: int,
        tags: list[str],
        category: str,
    ) -> bool:
        """
        Sync a document to the master index.

        Called after indexing to a domain index.

        Args:
            doc_id: Document ID
            source_index: Which domain index
            title: Document title
            summary: Document summary
            chunk_count: Number of chunks
            tags: Document tags
            category: Document category

        Returns:
            bool: True if synced
        """
        return await self.master.sync_from_domain_index(
            doc_id=doc_id,
            source_index=source_index,
            title=title,
            summary=summary,
            chunk_count=chunk_count,
            tags=tags,
            category=category,
        )

    async def delete_from_all(self, doc_id: str) -> dict[str, bool]:
        """
        Delete a document from all indexes.

        Args:
            doc_id: Document ID to delete

        Returns:
            Dict mapping index name to deletion success
        """
        results = {}

        # Delete from master
        results["master"] = await self.master.delete_document(doc_id)

        # Delete chunks from domain indexes
        for name, index in self._indexes.items():
            deleted = await index.delete_by_query({"term": {"doc_id": doc_id}})
            results[name] = deleted > 0

        return results
