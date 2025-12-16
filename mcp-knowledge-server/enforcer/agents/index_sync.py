"""IndexSyncAgent - Agent 5 of 5 in the Enforcer Pipeline.

Indexes validated content to OpenSearch with Titan embeddings.
Ensures content is searchable and metadata is complete.

Ultrathink Pattern:
1. Classification - Determine chunking strategy
2. Detection - Identify metadata fields
3. Validation - Verify indexing success
4. Output - Produce IndexResult
"""

import hashlib
import logging
import time
import uuid
from typing import Any

from ..models import (
    IndexResult,
    KnowledgeChunk,
    QualityResult,
    SemanticResult,
)
from ..quality_gates import (
    EnforcerGate,
    EnforcerGateResult,
    GateCategory,
)


logger = logging.getLogger(__name__)


# Chunking configuration
MAX_CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 100   # characters


class IndexSyncAgent:
    """Agent 5: Indexes content to OpenSearch.

    Quality Gates Enforced:
    - INDEX_EMBEDDING_GENERATED: Titan embedding created
    - INDEX_DOCUMENT_STORED: Stored in OpenSearch
    - INDEX_SEARCHABLE: Test query returns content
    - INDEX_METADATA_COMPLETE: All fields populated
    - INDEX_BATCH_COMPLETE: Batch items processed
    """

    def __init__(
        self,
        opensearch_client: Any = None,
        embedding_client: Any = None,
        index_name: str = "icda-knowledge",
    ):
        """Initialize the IndexSyncAgent.

        Args:
            opensearch_client: OpenSearch client.
            embedding_client: Bedrock/Titan embedding client.
            index_name: Name of the knowledge index.
        """
        self.opensearch_client = opensearch_client
        self.embedding_client = embedding_client
        self.index_name = index_name
        self.stats = {
            "processed": 0,
            "indexed": 0,
            "failed": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
        }

    async def process(
        self,
        raw_content: str,
        semantic: SemanticResult,
        quality: QualityResult,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[IndexResult, list[EnforcerGateResult]]:
        """Index content to OpenSearch.

        Ultrathink 4-Phase Analysis:
        1. Classification - Determine chunking strategy
        2. Detection - Extract metadata
        3. Validation - Verify indexing
        4. Output - Produce IndexResult

        Args:
            raw_content: Original content to index.
            semantic: Semantic extraction result.
            quality: Quality validation result.
            metadata: Additional metadata.

        Returns:
            Tuple of (IndexResult, list of gate results).
        """
        start_time = time.time()
        self.stats["processed"] += 1
        gates: list[EnforcerGateResult] = []

        # Generate document ID
        doc_id = self._generate_doc_id(raw_content)

        # Phase 1: Classification - Chunking strategy
        chunks = self._create_chunks(raw_content, doc_id)
        self.stats["chunks_created"] += len(chunks)
        logger.debug(f"Created {len(chunks)} chunks for document {doc_id}")

        # Phase 2: Detection - Build metadata
        index_metadata = self._build_metadata(
            semantic,
            quality,
            metadata or {},
        )

        # Phase 3: Indexing with quality gates
        embedding_success = False
        storage_success = False
        searchable = False

        # Gate 1: INDEX_EMBEDDING_GENERATED
        if self.embedding_client:
            try:
                for chunk in chunks:
                    embedding = await self._generate_embedding(chunk.content)
                    chunk.embedding = embedding
                    self.stats["embeddings_generated"] += 1
                embedding_success = True
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
                embedding_success = False
        else:
            # Mock success for testing without client
            embedding_success = True
            for chunk in chunks:
                chunk.embedding = [0.0] * 1024  # Mock embedding

        gates.append(EnforcerGateResult(
            gate=EnforcerGate.INDEX_EMBEDDING_GENERATED,
            passed=embedding_success,
            message="Embeddings generated successfully" if embedding_success
                    else "Failed to generate embeddings",
            details={"chunks": len(chunks), "embedding_dim": 1024},
            category=GateCategory.INDEX,
            severity="critical",
        ))

        # Gate 2: INDEX_DOCUMENT_STORED
        if embedding_success:
            if self.opensearch_client:
                try:
                    storage_success = await self._store_document(
                        doc_id,
                        chunks,
                        index_metadata,
                    )
                except Exception as e:
                    logger.error(f"Storage failed: {e}")
                    storage_success = False
            else:
                # Mock success for testing
                storage_success = True

        gates.append(EnforcerGateResult(
            gate=EnforcerGate.INDEX_DOCUMENT_STORED,
            passed=storage_success,
            message=f"Document {doc_id} stored" if storage_success
                    else "Failed to store document",
            details={"doc_id": doc_id, "chunks_stored": len(chunks) if storage_success else 0},
            category=GateCategory.INDEX,
            severity="critical",
        ))

        # Gate 3: INDEX_SEARCHABLE
        if storage_success:
            if self.opensearch_client:
                try:
                    searchable = await self._verify_searchable(doc_id)
                except Exception as e:
                    logger.warning(f"Search verification failed: {e}")
                    searchable = False
            else:
                # Mock success
                searchable = True

        gates.append(EnforcerGateResult(
            gate=EnforcerGate.INDEX_SEARCHABLE,
            passed=searchable,
            message="Content is searchable" if searchable
                    else "Content not yet searchable (may need refresh)",
            details={"doc_id": doc_id},
            category=GateCategory.INDEX,
            severity="warning",
        ))

        # Gate 4: INDEX_METADATA_COMPLETE
        required_fields = ["pr_relevant", "quality_score", "content_type"]
        present_fields = [f for f in required_fields if f in index_metadata]
        metadata_complete = len(present_fields) == len(required_fields)

        gates.append(EnforcerGateResult(
            gate=EnforcerGate.INDEX_METADATA_COMPLETE,
            passed=metadata_complete,
            message="All metadata fields populated" if metadata_complete
                    else f"Missing: {set(required_fields) - set(present_fields)}",
            details={"required": required_fields, "present": present_fields},
            category=GateCategory.INDEX,
            severity="info",
        ))

        # Phase 4: Output
        if storage_success:
            self.stats["indexed"] += 1
        else:
            self.stats["failed"] += 1

        elapsed_ms = int((time.time() - start_time) * 1000)

        result = IndexResult(
            success=storage_success,
            doc_id=doc_id if storage_success else None,
            chunks_created=len(chunks),
            embedding_generated=embedding_success,
            searchable=searchable,
            index_metadata=index_metadata,
        )

        return result, gates

    async def process_batch(
        self,
        items: list[dict[str, Any]],
    ) -> tuple[list[IndexResult], list[EnforcerGateResult]]:
        """Process a batch of items for indexing.

        Args:
            items: List of items to index.

        Returns:
            Tuple of (list of IndexResults, gate results).
        """
        results = []
        all_gates = []

        for item in items:
            result, gates = await self.process(
                raw_content=item.get("content", ""),
                semantic=item.get("semantic"),
                quality=item.get("quality"),
                metadata=item.get("metadata"),
            )
            results.append(result)
            all_gates.extend(gates)

        # Add batch completion gate
        successful = sum(1 for r in results if r.success)
        batch_complete = successful == len(items)

        all_gates.append(EnforcerGateResult(
            gate=EnforcerGate.INDEX_BATCH_COMPLETE,
            passed=batch_complete,
            message=f"Batch complete: {successful}/{len(items)}" if batch_complete
                    else f"Batch incomplete: {successful}/{len(items)} succeeded",
            details={"total": len(items), "successful": successful},
            category=GateCategory.INDEX,
            severity="critical",
        ))

        return results, all_gates

    def _generate_doc_id(self, content: str) -> str:
        """Generate unique document ID.

        Args:
            content: Content to hash.

        Returns:
            Unique document ID.
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"doc_{content_hash}_{uuid.uuid4().hex[:8]}"

    def _create_chunks(
        self,
        content: str,
        doc_id: str,
    ) -> list[KnowledgeChunk]:
        """Create chunks from content.

        Args:
            content: Content to chunk.
            doc_id: Parent document ID.

        Returns:
            List of chunks.
        """
        chunks = []

        # Simple chunking by paragraphs first
        paragraphs = content.split("\n\n")
        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if adding paragraph exceeds max size
            if len(current_chunk) + len(para) > MAX_CHUNK_SIZE:
                if current_chunk:
                    chunk_id = f"{doc_id}_chunk_{chunk_index}"
                    chunks.append(KnowledgeChunk(
                        chunk_id=chunk_id,
                        content=current_chunk.strip(),
                        source_doc_id=doc_id,
                        chunk_index=chunk_index,
                    ))
                    chunk_index += 1

                    # Start new chunk with overlap
                    overlap_start = max(0, len(current_chunk) - CHUNK_OVERLAP)
                    current_chunk = current_chunk[overlap_start:] + "\n\n" + para
                else:
                    current_chunk = para
            else:
                current_chunk += ("\n\n" if current_chunk else "") + para

        # Add final chunk
        if current_chunk.strip():
            chunk_id = f"{doc_id}_chunk_{chunk_index}"
            chunks.append(KnowledgeChunk(
                chunk_id=chunk_id,
                content=current_chunk.strip(),
                source_doc_id=doc_id,
                chunk_index=chunk_index,
            ))

        return chunks

    def _build_metadata(
        self,
        semantic: SemanticResult,
        quality: QualityResult,
        extra_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Build index metadata from results.

        Args:
            semantic: Semantic extraction result.
            quality: Quality validation result.
            extra_metadata: Additional metadata.

        Returns:
            Combined metadata dictionary.
        """
        metadata = {
            "pr_relevant": len(semantic.pr_patterns) > 0,
            "urbanization_mentioned": any(
                p.get("type") == "urbanization"
                for p in semantic.pr_patterns
            ),
            "quality_score": quality.overall_score,
            "entity_count": len(semantic.entities),
            "rule_count": len(semantic.rules),
            "pattern_count": len(semantic.patterns),
            "content_type": extra_metadata.get("content_type", "documentation"),
            "indexed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Merge extra metadata
        for key, value in extra_metadata.items():
            if key not in metadata:
                metadata[key] = value

        return metadata

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate Titan embedding for text.

        Args:
            text: Text to embed.

        Returns:
            1024-dimensional embedding vector.
        """
        if not self.embedding_client:
            # Return mock embedding
            return [0.0] * 1024

        try:
            response = await self.embedding_client.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                body={
                    "inputText": text[:8000],  # Titan limit
                    "dimensions": 1024,
                },
            )
            return response.get("embedding", [0.0] * 1024)
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise

    async def _store_document(
        self,
        doc_id: str,
        chunks: list[KnowledgeChunk],
        metadata: dict[str, Any],
    ) -> bool:
        """Store document and chunks in OpenSearch.

        Args:
            doc_id: Document ID.
            chunks: List of chunks to store.
            metadata: Document metadata.

        Returns:
            True if storage successful.
        """
        if not self.opensearch_client:
            return True  # Mock success

        try:
            # Store each chunk
            for chunk in chunks:
                doc_body = {
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "embedding": chunk.embedding,
                    "source_doc_id": doc_id,
                    "chunk_index": chunk.chunk_index,
                    **metadata,
                }

                await self.opensearch_client.index(
                    index=self.index_name,
                    id=chunk.chunk_id,
                    body=doc_body,
                )

            # Force refresh
            await self.opensearch_client.indices.refresh(index=self.index_name)

            return True

        except Exception as e:
            logger.error(f"Storage failed for {doc_id}: {e}")
            return False

    async def _verify_searchable(self, doc_id: str) -> bool:
        """Verify document is searchable.

        Args:
            doc_id: Document ID to search for.

        Returns:
            True if document is searchable.
        """
        if not self.opensearch_client:
            return True  # Mock success

        try:
            response = await self.opensearch_client.search(
                index=self.index_name,
                body={
                    "query": {
                        "term": {"source_doc_id": doc_id}
                    },
                    "size": 1,
                }
            )

            hits = response.get("hits", {}).get("total", {})
            if isinstance(hits, dict):
                return hits.get("value", 0) > 0
            return hits > 0

        except Exception as e:
            logger.warning(f"Search verification failed: {e}")
            return False

    def set_clients(
        self,
        opensearch_client: Any = None,
        embedding_client: Any = None,
    ) -> None:
        """Set the OpenSearch and embedding clients.

        Args:
            opensearch_client: OpenSearch client.
            embedding_client: Bedrock embedding client.
        """
        if opensearch_client:
            self.opensearch_client = opensearch_client
        if embedding_client:
            self.embedding_client = embedding_client

    def get_stats(self) -> dict[str, Any]:
        """Get agent statistics.

        Returns:
            Statistics dictionary.
        """
        return self.stats.copy()
