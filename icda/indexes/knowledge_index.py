"""
Knowledge Index - User-Facing RAG Index.

Stores documentation, guides, FAQs, and procedures for user queries.
Optimized for semantic search and retrieval augmented generation.

Features:
- Semantic chunking with overlap
- Multi-format document support
- Category and tag organization
- Audience-aware retrieval
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import logging

from .base_index import BaseIndex, IndexConfig, SearchResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class KnowledgeChunk:
    """A knowledge chunk to be indexed."""
    doc_id: str
    chunk_id: str
    filename: str
    chunk_index: int
    text: str
    tags: list[str] = field(default_factory=list)
    category: str = "general"
    audience: str = "user"  # "user", "admin", "developer"
    content_type: str = "document"  # "guide", "faq", "procedure", "reference"
    version: str = ""
    char_count: int = 0
    token_count: int = 0


class KnowledgeIndex(BaseIndex):
    """
    Knowledge index for user-facing RAG retrieval.

    Optimized for:
    - Documentation search
    - FAQ retrieval
    - Procedure lookup
    - Contextual answer generation

    Schema:
        - doc_id: Parent document ID
        - chunk_id: Unique chunk identifier
        - filename: Source file name
        - chunk_index: Position in document
        - text: Chunk content
        - tags: Categorization tags
        - category: Primary category
        - audience: Target audience
        - content_type: Type of content
        - version: Document version
        - embedding: Vector representation
    """

    def __init__(
        self,
        opensearch_client: Any,
        embedder: Any,
        index_name: str = "icda-knowledge",
    ):
        config = IndexConfig(
            name=index_name,
            shards=2,
            replicas=0,
        )
        super().__init__(opensearch_client, embedder, config)

    @property
    def mapping(self) -> dict[str, Any]:
        """OpenSearch mapping for the knowledge index."""
        return {
            "properties": {
                "doc_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "filename": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}},
                },
                "chunk_index": {"type": "integer"},
                "text": {
                    "type": "text",
                    "analyzer": "standard",
                },
                "tags": {"type": "keyword"},
                "category": {"type": "keyword"},
                "audience": {"type": "keyword"},
                "content_type": {"type": "keyword"},
                "version": {"type": "keyword"},
                "char_count": {"type": "integer"},
                "token_count": {"type": "integer"},
                "content_hash": {"type": "keyword"},
                "quality_score": {"type": "float"},
                "indexed_at": {"type": "date"},
                "embedding": {
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
            }
        }

    async def index_knowledge_chunk(
        self,
        chunk: KnowledgeChunk,
        quality_score: float = 1.0,
        generate_embedding: bool = True,
    ) -> bool:
        """
        Index a knowledge chunk.

        Args:
            chunk: KnowledgeChunk to index
            quality_score: Quality score from enforcer (0-1)
            generate_embedding: Whether to generate embedding

        Returns:
            bool: True if indexed successfully
        """
        document = {
            "doc_id": chunk.doc_id,
            "chunk_id": chunk.chunk_id,
            "filename": chunk.filename,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "tags": chunk.tags,
            "category": chunk.category,
            "audience": chunk.audience,
            "content_type": chunk.content_type,
            "version": chunk.version,
            "char_count": chunk.char_count or len(chunk.text),
            "token_count": chunk.token_count,
            "content_hash": self.generate_content_hash(chunk.text),
            "quality_score": quality_score,
            "indexed_at": datetime.utcnow().isoformat(),
        }

        # Generate embedding
        if generate_embedding:
            embedding = await self.generate_embedding(chunk.text[:8000])
            if embedding:
                document["embedding"] = embedding

        return await self.index_document(chunk.chunk_id, document, refresh=True)

    async def index_document_chunks(
        self,
        doc_id: str,
        filename: str,
        chunks: list[dict[str, Any]],
        tags: list[str] = None,
        category: str = "general",
        audience: str = "user",
        content_type: str = "document",
        quality_scores: Optional[list[float]] = None,
    ) -> tuple[int, int]:
        """
        Index multiple chunks from a document.

        Args:
            doc_id: Document identifier
            filename: Source filename
            chunks: List of chunk dicts with 'text' and optional 'token_count'
            tags: Document tags
            category: Document category
            audience: Target audience
            content_type: Type of content
            quality_scores: Optional per-chunk quality scores

        Returns:
            tuple: (success_count, error_count)
        """
        # Delete existing chunks for this document
        await self.delete_by_query({"term": {"doc_id": doc_id}})

        success = 0
        errors = 0

        for i, chunk_data in enumerate(chunks):
            text = chunk_data.get("text", "")
            if not text.strip():
                continue

            chunk = KnowledgeChunk(
                doc_id=doc_id,
                chunk_id=f"{doc_id}_chunk_{i}",
                filename=filename,
                chunk_index=i,
                text=text,
                tags=tags or [],
                category=category,
                audience=audience,
                content_type=content_type,
                char_count=len(text),
                token_count=chunk_data.get("token_count", 0),
            )

            quality = quality_scores[i] if quality_scores and i < len(quality_scores) else 1.0

            if await self.index_knowledge_chunk(chunk, quality_score=quality):
                success += 1
            else:
                errors += 1

        return success, errors

    async def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        audience: Optional[str] = None,
        content_type: Optional[str] = None,
        min_quality: float = 0.0,
        k: int = 10,
    ) -> list[SearchResult]:
        """
        Search the knowledge base.

        Args:
            query: Search query
            category: Filter by category
            tags: Filter by tags (any match)
            audience: Filter by audience
            content_type: Filter by content type
            min_quality: Minimum quality score
            k: Number of results

        Returns:
            List of search results
        """
        # Build filters
        filters: list[dict[str, Any]] = []

        if category:
            filters.append({"term": {"category": category}})

        if tags:
            filters.append({"terms": {"tags": tags}})

        if audience:
            filters.append({"term": {"audience": audience}})

        if content_type:
            filters.append({"term": {"content_type": content_type}})

        if min_quality > 0:
            filters.append({"range": {"quality_score": {"gte": min_quality}}})

        filter_query = {"bool": {"must": filters}} if filters else None

        # Generate query embedding
        embedding = await self.generate_embedding(query)

        if embedding:
            return await self.knn_search(
                embedding=embedding,
                k=k,
                filters=filter_query,
            )
        else:
            # Fallback to text search
            text_query: dict[str, Any] = {
                "bool": {
                    "must": [
                        {"match": {"text": query}},
                    ],
                }
            }

            if filter_query:
                text_query["bool"]["filter"] = filter_query["bool"]["must"]

            return await self.search(text_query, size=k)

    async def get_document_chunks(
        self,
        doc_id: str,
        ordered: bool = True,
    ) -> list[SearchResult]:
        """
        Get all chunks for a document.

        Args:
            doc_id: Document ID
            ordered: Whether to order by chunk_index

        Returns:
            List of chunks
        """
        query = {"term": {"doc_id": doc_id}}

        results = await self.search(query, size=1000)

        if ordered:
            results.sort(key=lambda r: r.metadata.get("chunk_index", 0))

        return results

    async def get_by_tags(
        self,
        tags: list[str],
        match_all: bool = False,
        k: int = 50,
    ) -> list[SearchResult]:
        """
        Get chunks by tags.

        Args:
            tags: Tags to match
            match_all: Require all tags (vs any)
            k: Maximum results

        Returns:
            List of matching chunks
        """
        if match_all:
            query = {
                "bool": {
                    "must": [{"term": {"tags": tag}} for tag in tags]
                }
            }
        else:
            query = {"terms": {"tags": tags}}

        return await self.search(query, size=k)

    async def get_categories(self) -> dict[str, int]:
        """Get all categories with document counts."""
        stats = await self.get_stats()
        return stats.categories

    async def get_tags(self) -> dict[str, int]:
        """Get all tags with document counts."""
        stats = await self.get_stats()
        return stats.tags

    async def update_quality_score(
        self,
        chunk_id: str,
        quality_score: float,
    ) -> bool:
        """
        Update the quality score for a chunk.

        Args:
            chunk_id: Chunk ID
            quality_score: New quality score (0-1)

        Returns:
            bool: True if updated
        """
        if not self.available:
            return False

        try:
            await self.client.update(
                index=self.index_name,
                id=chunk_id,
                body={
                    "doc": {"quality_score": quality_score},
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update quality score for {chunk_id}: {e}")
            return False

    async def get_low_quality_chunks(
        self,
        threshold: float = 0.5,
        limit: int = 100,
    ) -> list[SearchResult]:
        """
        Get chunks with quality scores below threshold.

        Useful for admin review and cleanup.

        Args:
            threshold: Quality score threshold
            limit: Maximum results

        Returns:
            List of low-quality chunks
        """
        query = {
            "bool": {
                "must": [
                    {"range": {"quality_score": {"lt": threshold}}},
                ]
            }
        }

        return await self.search(query, size=limit)

    async def get_unique_documents(self) -> list[dict[str, Any]]:
        """
        Get list of unique documents in the index.

        Returns:
            List of document info dicts
        """
        if not self.available:
            return []

        try:
            result = await self.client.search(
                index=self.index_name,
                body={
                    "size": 0,
                    "aggs": {
                        "docs": {
                            "terms": {
                                "field": "doc_id",
                                "size": 10000,
                            },
                            "aggs": {
                                "filename": {
                                    "terms": {"field": "filename.keyword", "size": 1}
                                },
                                "category": {
                                    "terms": {"field": "category", "size": 1}
                                },
                                "chunk_count": {
                                    "value_count": {"field": "chunk_id"}
                                },
                            },
                        }
                    },
                },
            )

            docs = []
            for bucket in result.get("aggregations", {}).get("docs", {}).get("buckets", []):
                doc_id = bucket["key"]
                filename_buckets = bucket.get("filename", {}).get("buckets", [])
                category_buckets = bucket.get("category", {}).get("buckets", [])

                docs.append({
                    "doc_id": doc_id,
                    "filename": filename_buckets[0]["key"] if filename_buckets else "unknown",
                    "category": category_buckets[0]["key"] if category_buckets else "general",
                    "chunk_count": bucket.get("chunk_count", {}).get("value", 0),
                })

            return docs

        except Exception as e:
            logger.error(f"Failed to get unique documents: {e}")
            return []
