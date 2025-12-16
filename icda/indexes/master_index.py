"""
Master Index - Router/Summary Index.

The master index stores document summaries and routing metadata for fast
query routing across the federated index hierarchy.

Features:
- Document summaries with embeddings for routing
- Tracks which domain index contains full content
- Popularity scoring for result ranking
- Cross-references between related documents
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import logging

from .base_index import BaseIndex, IndexConfig, SearchResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MasterDocument:
    """A document entry in the master index."""
    doc_id: str
    source_index: str  # "code", "knowledge", "customers"
    doc_type: str  # "code", "guide", "faq", "customer", etc.
    title: str
    summary: str
    chunk_count: int = 0
    tags: list[str] = field(default_factory=list)
    category: str = "general"
    access_level: str = "public"  # "public", "internal", "dev"
    popularity_score: float = 0.0
    cross_references: list[str] = field(default_factory=list)
    indexed_at: Optional[str] = None


class MasterIndex(BaseIndex):
    """
    Master index for query routing and document discovery.

    Stores document summaries with embeddings for fast semantic routing.
    Used by IndexFederation to determine which domain indexes to search.

    Schema:
        - doc_id: Unique document identifier
        - source_index: Which domain index has full content
        - doc_type: Type classification
        - title: Document title
        - summary: AI-generated or extracted summary
        - summary_embedding: Vector for routing
        - chunk_count: Number of chunks in source index
        - tags: Routing tags
        - category: Primary category
        - access_level: Access control (public/internal/dev)
        - popularity_score: Query hit tracking
        - cross_references: Related document IDs
    """

    EMBEDDING_FIELD = "summary_embedding"

    def __init__(
        self,
        opensearch_client: Any,
        embedder: Any,
        index_name: str = "icda-master",
    ):
        config = IndexConfig(
            name=index_name,
            shards=1,
            replicas=0,
        )
        super().__init__(opensearch_client, embedder, config)

    @property
    def mapping(self) -> dict[str, Any]:
        """OpenSearch mapping for the master index."""
        return {
            "properties": {
                "doc_id": {"type": "keyword"},
                "source_index": {"type": "keyword"},
                "doc_type": {"type": "keyword"},
                "title": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}},
                },
                "summary": {"type": "text"},
                "summary_embedding": {
                    "type": "knn_vector",
                    "dimension": self.EMBEDDING_DIMENSION,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                        "parameters": {
                            "ef_construction": 128,
                            "m": 24,
                        },
                    },
                },
                "chunk_count": {"type": "integer"},
                "tags": {"type": "keyword"},
                "category": {"type": "keyword"},
                "access_level": {"type": "keyword"},
                "popularity_score": {"type": "float"},
                "cross_references": {"type": "keyword"},
                "indexed_at": {"type": "date"},
            }
        }

    async def index_master_document(
        self,
        doc: MasterDocument,
        generate_embedding: bool = True,
    ) -> bool:
        """
        Index a document summary to the master index.

        Args:
            doc: MasterDocument to index
            generate_embedding: Whether to generate embedding for summary

        Returns:
            bool: True if indexed successfully
        """
        document = {
            "doc_id": doc.doc_id,
            "source_index": doc.source_index,
            "doc_type": doc.doc_type,
            "title": doc.title,
            "summary": doc.summary,
            "chunk_count": doc.chunk_count,
            "tags": doc.tags,
            "category": doc.category,
            "access_level": doc.access_level,
            "popularity_score": doc.popularity_score,
            "cross_references": doc.cross_references,
            "indexed_at": doc.indexed_at or datetime.utcnow().isoformat(),
        }

        # Generate embedding for summary
        if generate_embedding and doc.summary:
            embedding = await self.generate_embedding(doc.summary)
            if embedding:
                document["summary_embedding"] = embedding

        return await self.index_document(doc.doc_id, document, refresh=True)

    async def route_query(
        self,
        query: str,
        k: int = 5,
        access_levels: Optional[list[str]] = None,
    ) -> list[tuple[str, float]]:
        """
        Route a query to determine which indexes to search.

        Args:
            query: Search query
            k: Number of top routing hints
            access_levels: Filter by access levels

        Returns:
            List of (source_index, relevance_score) tuples
        """
        # Generate query embedding
        embedding = await self.generate_embedding(query)
        if not embedding:
            # Fallback to keyword-based routing
            return await self._keyword_route(query)

        # Build filter
        filters = None
        if access_levels:
            filters = {"terms": {"access_level": access_levels}}

        # KNN search on summaries
        results = await self.knn_search(
            embedding=embedding,
            k=k,
            filters=filters,
        )

        # Aggregate scores by source index
        index_scores: dict[str, list[float]] = {}
        for result in results:
            source = result.metadata.get("source_index", "unknown")
            index_scores.setdefault(source, []).append(result.score)

        # Calculate average score per index
        routing = [
            (idx, sum(scores) / len(scores))
            for idx, scores in index_scores.items()
        ]

        # Sort by score descending
        routing.sort(key=lambda x: x[1], reverse=True)

        return routing

    async def _keyword_route(self, query: str) -> list[tuple[str, float]]:
        """Fallback keyword-based routing when embeddings unavailable."""
        # Simple keyword matching for routing
        query_lower = query.lower()

        scores = {
            "code": 0.0,
            "knowledge": 0.0,
            "customers": 0.0,
        }

        # Code-related keywords
        code_keywords = ["code", "function", "class", "api", "implement", "bug", "error", "debug"]
        for kw in code_keywords:
            if kw in query_lower:
                scores["code"] += 0.3

        # Knowledge-related keywords
        knowledge_keywords = ["how", "what", "guide", "help", "procedure", "policy", "rule"]
        for kw in knowledge_keywords:
            if kw in query_lower:
                scores["knowledge"] += 0.3

        # Customer-related keywords
        customer_keywords = ["customer", "crid", "address", "lookup", "find", "search", "who"]
        for kw in customer_keywords:
            if kw in query_lower:
                scores["customers"] += 0.3

        # Normalize and return
        routing = [(idx, min(1.0, score)) for idx, score in scores.items() if score > 0]
        routing.sort(key=lambda x: x[1], reverse=True)

        # If no keywords matched, return all indexes with equal weight
        if not routing:
            routing = [("knowledge", 0.5), ("code", 0.3), ("customers", 0.2)]

        return routing

    async def increment_popularity(self, doc_id: str, increment: float = 0.1) -> bool:
        """
        Increment the popularity score for a document.

        Called when a document's chunks are retrieved in search results.

        Args:
            doc_id: Document ID
            increment: Score increment (default 0.1)

        Returns:
            bool: True if updated
        """
        if not self.available:
            return False

        try:
            await self.client.update(
                index=self.index_name,
                id=doc_id,
                body={
                    "script": {
                        "source": "ctx._source.popularity_score += params.inc",
                        "params": {"inc": increment},
                    }
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update popularity for {doc_id}: {e}")
            return False

    async def get_related_documents(
        self,
        doc_id: str,
        k: int = 5,
    ) -> list[SearchResult]:
        """
        Get documents related to a given document.

        Uses cross-references and semantic similarity.

        Args:
            doc_id: Source document ID
            k: Number of related docs to return

        Returns:
            List of related documents
        """
        # Get the source document
        doc = await self.get_document(doc_id)
        if not doc:
            return []

        related: list[SearchResult] = []

        # First, get explicit cross-references
        cross_refs = doc.get("cross_references", [])
        for ref_id in cross_refs[:k]:
            ref_doc = await self.get_document(ref_id)
            if ref_doc:
                related.append(SearchResult(
                    doc_id=ref_id,
                    chunk_id=ref_id,
                    text=ref_doc.get("summary", ""),
                    score=1.0,  # Explicit reference
                    source_index=ref_doc.get("source_index", ""),
                    metadata=ref_doc,
                ))

        # If we need more, do semantic similarity
        if len(related) < k:
            embedding = doc.get("summary_embedding")
            if embedding:
                similar = await self.knn_search(
                    embedding=embedding,
                    k=k - len(related) + 1,  # +1 to exclude self
                )
                # Filter out the source doc and already-found docs
                found_ids = {doc_id} | {r.doc_id for r in related}
                for result in similar:
                    if result.doc_id not in found_ids:
                        related.append(result)
                        if len(related) >= k:
                            break

        return related[:k]

    async def sync_from_domain_index(
        self,
        doc_id: str,
        source_index: str,
        title: str,
        summary: str,
        chunk_count: int,
        tags: list[str],
        category: str,
        doc_type: str = "document",
        access_level: str = "public",
    ) -> bool:
        """
        Sync a document from a domain index to the master index.

        Called when a document is indexed in a domain index.

        Args:
            doc_id: Document ID
            source_index: Which domain index (code/knowledge/customers)
            title: Document title
            summary: Document summary
            chunk_count: Number of chunks
            tags: Document tags
            category: Document category
            doc_type: Type of document
            access_level: Access level

        Returns:
            bool: True if synced successfully
        """
        doc = MasterDocument(
            doc_id=doc_id,
            source_index=source_index,
            doc_type=doc_type,
            title=title,
            summary=summary,
            chunk_count=chunk_count,
            tags=tags,
            category=category,
            access_level=access_level,
            indexed_at=datetime.utcnow().isoformat(),
        )

        return await self.index_master_document(doc)

    async def get_index_distribution(self) -> dict[str, int]:
        """
        Get document count per source index.

        Returns:
            Dict mapping source_index to document count
        """
        if not self.available:
            return {}

        try:
            result = await self.client.search(
                index=self.index_name,
                body={
                    "size": 0,
                    "aggs": {
                        "by_index": {
                            "terms": {"field": "source_index", "size": 10}
                        }
                    },
                },
            )

            buckets = result.get("aggregations", {}).get("by_index", {}).get("buckets", [])
            return {b["key"]: b["doc_count"] for b in buckets}

        except Exception as e:
            logger.error(f"Failed to get index distribution: {e}")
            return {}
