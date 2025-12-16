"""
Base Index Abstract Class.

Provides common functionality for all ICDA indexes including:
- Index creation and mapping management
- CRUD operations for documents
- Health checks and statistics
- Embedding integration

All specific indexes inherit from this base.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import hashlib
import logging

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IndexConfig:
    """Configuration for an index."""
    name: str
    shards: int = 1
    replicas: int = 0
    refresh_interval: str = "1s"
    max_result_window: int = 10000


@dataclass(slots=True)
class IndexStats:
    """Statistics for an index."""
    name: str
    doc_count: int = 0
    chunk_count: int = 0
    storage_bytes: int = 0
    health: str = "unknown"  # green, yellow, red, unknown
    last_updated: Optional[str] = None
    categories: dict[str, int] = field(default_factory=dict)
    tags: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class SearchResult:
    """A single search result."""
    doc_id: str
    chunk_id: str
    text: str
    score: float
    source_index: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseIndex(ABC):
    """
    Abstract base class for all ICDA indexes.

    Provides common functionality for OpenSearch index management.
    Subclasses must implement the mapping property and any custom logic.

    Args:
        opensearch_client: AsyncOpenSearch client instance
        embedder: Embedding client for generating vectors
        config: Index configuration
    """

    __slots__ = ("client", "embedder", "config", "available", "_stats_cache", "_stats_time")

    # Subclasses should override these
    EMBEDDING_DIMENSION = 1024
    EMBEDDING_FIELD = "embedding"

    def __init__(
        self,
        opensearch_client: Any,
        embedder: Any,
        config: IndexConfig,
    ):
        self.client = opensearch_client
        self.embedder = embedder
        self.config = config
        self.available = opensearch_client is not None
        self._stats_cache: Optional[IndexStats] = None
        self._stats_time: Optional[datetime] = None

    @property
    @abstractmethod
    def mapping(self) -> dict[str, Any]:
        """
        Return the OpenSearch mapping for this index.

        Must be implemented by subclasses.

        Returns:
            dict: OpenSearch mapping configuration
        """
        pass

    @property
    def index_name(self) -> str:
        """Return the index name."""
        return self.config.name

    async def ensure_index(self) -> bool:
        """
        Ensure the index exists, creating it if needed.

        Returns:
            bool: True if index exists or was created successfully
        """
        if not self.available:
            logger.warning(f"OpenSearch not available - {self.index_name} index disabled")
            return False

        try:
            exists = await self.client.indices.exists(index=self.index_name)
            if not exists:
                logger.info(f"Creating index: {self.index_name}")
                await self.client.indices.create(
                    index=self.index_name,
                    body=self._build_index_body(),
                )
                logger.info(f"Index created: {self.index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to ensure index {self.index_name}: {e}")
            return False

    def _build_index_body(self) -> dict[str, Any]:
        """Build the full index creation body with settings and mappings."""
        return {
            "settings": {
                "index": {
                    "knn": True,
                    "number_of_shards": self.config.shards,
                    "number_of_replicas": self.config.replicas,
                    "refresh_interval": self.config.refresh_interval,
                    "max_result_window": self.config.max_result_window,
                },
            },
            "mappings": self.mapping,
        }

    async def delete_index(self) -> bool:
        """
        Delete the index entirely.

        Returns:
            bool: True if deleted successfully
        """
        if not self.available:
            return False

        try:
            exists = await self.client.indices.exists(index=self.index_name)
            if exists:
                await self.client.indices.delete(index=self.index_name)
                logger.info(f"Index deleted: {self.index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete index {self.index_name}: {e}")
            return False

    async def index_document(
        self,
        doc_id: str,
        document: dict[str, Any],
        refresh: bool = False,
    ) -> bool:
        """
        Index a single document.

        Args:
            doc_id: Document ID
            document: Document body
            refresh: Whether to refresh immediately

        Returns:
            bool: True if indexed successfully
        """
        if not self.available:
            return False

        try:
            await self.client.index(
                index=self.index_name,
                id=doc_id,
                body=document,
                refresh=refresh,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to index document {doc_id}: {e}")
            return False

    async def bulk_index(
        self,
        documents: list[tuple[str, dict[str, Any]]],
        refresh: bool = True,
    ) -> tuple[int, int]:
        """
        Bulk index multiple documents.

        Args:
            documents: List of (doc_id, document) tuples
            refresh: Whether to refresh after bulk

        Returns:
            tuple: (success_count, error_count)
        """
        if not self.available or not documents:
            return 0, len(documents)

        try:
            from opensearchpy.helpers import async_bulk

            actions = [
                {
                    "_index": self.index_name,
                    "_id": doc_id,
                    "_source": doc,
                }
                for doc_id, doc in documents
            ]

            success, errors = await async_bulk(
                self.client,
                actions,
                raise_on_error=False,
                refresh=refresh,
            )

            error_count = len(errors) if isinstance(errors, list) else 0
            return success, error_count

        except Exception as e:
            logger.error(f"Bulk index failed: {e}")
            return 0, len(documents)

    async def get_document(self, doc_id: str) -> Optional[dict[str, Any]]:
        """
        Get a document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Document source or None if not found
        """
        if not self.available:
            return None

        try:
            result = await self.client.get(
                index=self.index_name,
                id=doc_id,
            )
            return result.get("_source")
        except Exception:
            return None

    async def delete_document(self, doc_id: str, refresh: bool = False) -> bool:
        """
        Delete a document by ID.

        Args:
            doc_id: Document ID
            refresh: Whether to refresh immediately

        Returns:
            bool: True if deleted
        """
        if not self.available:
            return False

        try:
            await self.client.delete(
                index=self.index_name,
                id=doc_id,
                refresh=refresh,
            )
            return True
        except Exception:
            return False

    async def delete_by_query(
        self,
        query: dict[str, Any],
        refresh: bool = True,
    ) -> int:
        """
        Delete documents matching a query.

        Args:
            query: OpenSearch query DSL
            refresh: Whether to refresh after

        Returns:
            int: Number of documents deleted
        """
        if not self.available:
            return 0

        try:
            result = await self.client.delete_by_query(
                index=self.index_name,
                body={"query": query},
                refresh=refresh,
            )
            return result.get("deleted", 0)
        except Exception as e:
            logger.error(f"Delete by query failed: {e}")
            return 0

    async def search(
        self,
        query: dict[str, Any],
        size: int = 10,
        from_: int = 0,
        source_includes: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """
        Execute a search query.

        Args:
            query: OpenSearch query DSL
            size: Number of results
            from_: Offset for pagination
            source_includes: Fields to include in response

        Returns:
            List of SearchResult objects
        """
        if not self.available:
            return []

        try:
            body: dict[str, Any] = {
                "query": query,
                "size": size,
                "from": from_,
            }

            if source_includes:
                body["_source"] = {"includes": source_includes}

            result = await self.client.search(
                index=self.index_name,
                body=body,
            )

            hits = result.get("hits", {}).get("hits", [])
            return [
                SearchResult(
                    doc_id=hit.get("_source", {}).get("doc_id", hit["_id"]),
                    chunk_id=hit["_id"],
                    text=hit.get("_source", {}).get("text", ""),
                    score=hit.get("_score", 0.0),
                    source_index=self.index_name,
                    metadata=hit.get("_source", {}),
                )
                for hit in hits
            ]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def knn_search(
        self,
        embedding: list[float],
        k: int = 10,
        filters: Optional[dict[str, Any]] = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """
        Execute a k-NN vector search.

        Args:
            embedding: Query embedding vector
            k: Number of results
            filters: Optional filters to apply
            min_score: Minimum score threshold

        Returns:
            List of SearchResult objects
        """
        if not self.available:
            return []

        try:
            knn_query: dict[str, Any] = {
                "knn": {
                    self.EMBEDDING_FIELD: {
                        "vector": embedding,
                        "k": k,
                    }
                }
            }

            if filters:
                knn_query["knn"][self.EMBEDDING_FIELD]["filter"] = filters

            result = await self.client.search(
                index=self.index_name,
                body={
                    "query": knn_query,
                    "size": k,
                    "min_score": min_score,
                },
            )

            hits = result.get("hits", {}).get("hits", [])
            return [
                SearchResult(
                    doc_id=hit.get("_source", {}).get("doc_id", hit["_id"]),
                    chunk_id=hit["_id"],
                    text=hit.get("_source", {}).get("text", ""),
                    score=hit.get("_score", 0.0),
                    source_index=self.index_name,
                    metadata=hit.get("_source", {}),
                )
                for hit in hits
            ]

        except Exception as e:
            logger.error(f"KNN search failed: {e}")
            return []

    async def get_stats(self, use_cache: bool = True) -> IndexStats:
        """
        Get index statistics.

        Args:
            use_cache: Whether to use cached stats (5 minute cache)

        Returns:
            IndexStats object
        """
        # Check cache
        if use_cache and self._stats_cache and self._stats_time:
            age = (datetime.utcnow() - self._stats_time).total_seconds()
            if age < 300:  # 5 minute cache
                return self._stats_cache

        stats = IndexStats(name=self.index_name)

        if not self.available:
            stats.health = "unavailable"
            return stats

        try:
            # Get index stats
            index_stats = await self.client.indices.stats(index=self.index_name)
            primaries = index_stats.get("_all", {}).get("primaries", {})

            stats.doc_count = primaries.get("docs", {}).get("count", 0)
            stats.storage_bytes = primaries.get("store", {}).get("size_in_bytes", 0)

            # Get health
            health = await self.client.cluster.health(index=self.index_name)
            stats.health = health.get("status", "unknown")

            # Get aggregations for categories/tags if available
            agg_result = await self.client.search(
                index=self.index_name,
                body={
                    "size": 0,
                    "aggs": {
                        "categories": {
                            "terms": {"field": "category", "size": 50}
                        },
                        "tags": {
                            "terms": {"field": "tags", "size": 100}
                        },
                    },
                },
            )

            aggs = agg_result.get("aggregations", {})
            stats.categories = {
                b["key"]: b["doc_count"]
                for b in aggs.get("categories", {}).get("buckets", [])
            }
            stats.tags = {
                b["key"]: b["doc_count"]
                for b in aggs.get("tags", {}).get("buckets", [])
            }

            stats.last_updated = datetime.utcnow().isoformat()

            # Cache stats
            self._stats_cache = stats
            self._stats_time = datetime.utcnow()

        except Exception as e:
            logger.error(f"Failed to get stats for {self.index_name}: {e}")
            stats.health = "error"

        return stats

    async def refresh(self) -> bool:
        """
        Refresh the index to make changes searchable.

        Returns:
            bool: True if refreshed successfully
        """
        if not self.available:
            return False

        try:
            await self.client.indices.refresh(index=self.index_name)
            return True
        except Exception as e:
            logger.error(f"Failed to refresh {self.index_name}: {e}")
            return False

    async def count(self, query: Optional[dict[str, Any]] = None) -> int:
        """
        Count documents in the index.

        Args:
            query: Optional filter query

        Returns:
            int: Document count
        """
        if not self.available:
            return 0

        try:
            body = {"query": query} if query else {"query": {"match_all": {}}}
            result = await self.client.count(index=self.index_name, body=body)
            return result.get("count", 0)
        except Exception:
            return 0

    @staticmethod
    def generate_content_hash(content: str) -> str:
        """
        Generate a hash for content deduplication.

        Args:
            content: Text content

        Returns:
            str: SHA256 hash (first 16 chars)
        """
        normalized = " ".join(content.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    async def generate_embedding(self, text: str) -> Optional[list[float]]:
        """
        Generate embedding for text using the configured embedder.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        if not self.embedder:
            return None

        try:
            # Handle different embedder interfaces
            if hasattr(self.embedder, "embed"):
                return await self.embedder.embed(text)
            elif hasattr(self.embedder, "generate_embedding"):
                return self.embedder.generate_embedding(text)
            else:
                return self.embedder(text)
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None