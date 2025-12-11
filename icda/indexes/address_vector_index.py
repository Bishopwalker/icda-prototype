"""Vector index for semantic address search.

Uses OpenSearch kNN for semantic similarity matching of addresses,
enabling fuzzy matching based on meaning rather than exact text.
"""

import logging
from typing import Any

import boto3
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection, AWSV4SignerAsyncAuth

from icda.embeddings import EmbeddingClient
from icda.address_models import ParsedAddress

logger = logging.getLogger(__name__)


class AddressVectorIndex:
    """Vector-based semantic address search using OpenSearch.

    Indexes addresses with embeddings for semantic similarity search,
    enabling matches even with typos, abbreviations, or variations.
    """

    INDEX_MAPPING = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "address_text": {"type": "text"},
                "street_number": {"type": "keyword"},
                "street_name": {"type": "text"},
                "street_type": {"type": "keyword"},
                "city": {"type": "keyword"},
                "state": {"type": "keyword"},
                "zip_code": {"type": "keyword"},
                "customer_id": {"type": "keyword"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    }
                }
            }
        }
    }

    def __init__(self, embedder: EmbeddingClient, index_name: str = "icda-addresses"):
        """Initialize address vector index.

        Args:
            embedder: Embedding client for generating vectors.
            index_name: OpenSearch index name.
        """
        self.embedder = embedder
        self.index_name = index_name
        self.client: AsyncOpenSearch | None = None
        self.available = False
        self.is_serverless = False

    async def connect(self, host: str, region: str) -> bool:
        """Connect to OpenSearch.

        Args:
            host: OpenSearch host URL.
            region: AWS region.

        Returns:
            True if connection successful.
        """
        if not host:
            logger.info("No OpenSearch host configured for address vector index")
            return False

        self.is_serverless = "aoss.amazonaws.com" in host
        is_aws = "amazonaws.com" in host

        try:
            if is_aws:
                credentials = boto3.Session().get_credentials()
                service = "aoss" if self.is_serverless else "es"

                self.client = AsyncOpenSearch(
                    hosts=[{"host": host, "port": 443}],
                    http_auth=AWSV4SignerAsyncAuth(credentials, region, service),
                    use_ssl=True,
                    verify_certs=True,
                    connection_class=AsyncHttpConnection,
                )
            else:
                self.client = AsyncOpenSearch(
                    hosts=[host],
                    use_ssl=False,
                    verify_certs=False,
                    connection_class=AsyncHttpConnection,
                )

            # Test connection
            if self.is_serverless:
                await self.client.indices.get_alias()
            else:
                await self.client.info()

            self.available = True
            logger.info(f"Address vector index connected: {host}")

            # Ensure index exists
            await self._ensure_index()

            return True

        except Exception as e:
            logger.warning(f"Address vector index connection failed: {e}")
            self.available = False
            return False

    async def _ensure_index(self) -> None:
        """Create index if it doesn't exist."""
        if not self.client:
            return

        try:
            if not await self.client.indices.exists(index=self.index_name):
                await self.client.indices.create(
                    index=self.index_name,
                    body=self.INDEX_MAPPING,
                )
                logger.info(f"Created address vector index: {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to create address vector index: {e}")

    async def close(self) -> None:
        """Close the connection."""
        if self.client:
            await self.client.close()
            self.client = None
            self.available = False

    async def index_address(
        self,
        parsed: ParsedAddress,
        customer_id: str,
    ) -> bool:
        """Index a single address.

        Args:
            parsed: Parsed address to index.
            customer_id: Associated customer ID.

        Returns:
            True if indexing successful.
        """
        if not self.available:
            return False

        # Create searchable text
        address_text = self._create_address_text(parsed)

        # Generate embedding
        embedding = self.embedder.embed(address_text)
        if not embedding:
            return False

        doc = {
            "address_text": address_text,
            "street_number": parsed.street_number,
            "street_name": parsed.street_name,
            "street_type": parsed.street_type,
            "city": parsed.city,
            "state": parsed.state,
            "zip_code": parsed.zip_code,
            "customer_id": customer_id,
            "embedding": embedding,
        }

        try:
            await self.client.index(index=self.index_name, body=doc)
            return True
        except Exception as e:
            logger.error(f"Failed to index address: {e}")
            return False

    async def search_semantic(
        self,
        query: str,
        limit: int = 10,
        state_filter: str = None,
        zip_filter: str = None,
    ) -> list[dict[str, Any]]:
        """Search for addresses semantically.

        Args:
            query: Natural language query or partial address.
            limit: Maximum results to return.
            state_filter: Optional state to filter by.
            zip_filter: Optional ZIP to filter by.

        Returns:
            List of matching addresses with scores.
        """
        if not self.available:
            return []

        embedding = self.embedder.embed(query)
        if not embedding:
            return []

        # Build filter clauses
        must_clauses = []
        if state_filter:
            must_clauses.append({"term": {"state": state_filter.upper()}})
        if zip_filter:
            must_clauses.append({"term": {"zip_code": zip_filter}})

        # KNN query with optional filters
        if must_clauses:
            search_body = {
                "size": limit,
                "query": {
                    "bool": {
                        "must": must_clauses,
                        "should": [
                            {"knn": {"embedding": {"vector": embedding, "k": limit * 2}}}
                        ]
                    }
                }
            }
        else:
            search_body = {
                "size": limit,
                "query": {"knn": {"embedding": {"vector": embedding, "k": limit}}}
            }

        try:
            resp = await self.client.search(index=self.index_name, body=search_body)
            hits = resp["hits"]["hits"]

            results = []
            for hit in hits:
                source = hit["_source"]
                results.append({
                    "address_text": source.get("address_text"),
                    "street_number": source.get("street_number"),
                    "street_name": source.get("street_name"),
                    "street_type": source.get("street_type"),
                    "city": source.get("city"),
                    "state": source.get("state"),
                    "zip_code": source.get("zip_code"),
                    "customer_id": source.get("customer_id"),
                    "score": round(hit["_score"], 4),
                })

            return results

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def search_multi_state(
        self,
        query: str,
        states: list[str],
        limit_per_state: int = 5,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search for addresses across multiple states.

        Args:
            query: Search query.
            states: List of state codes to search.
            limit_per_state: Max results per state.

        Returns:
            Dict mapping state -> list of results.
        """
        results = {}

        for state in states:
            state_results = await self.search_semantic(
                query,
                limit=limit_per_state,
                state_filter=state,
            )
            if state_results:
                results[state] = state_results

        return results

    def _create_address_text(self, parsed: ParsedAddress) -> str:
        """Create searchable text from parsed address."""
        parts = []

        if parsed.street_number:
            parts.append(parsed.street_number)
        if parsed.street_name:
            parts.append(parsed.street_name)
        if parsed.street_type:
            parts.append(parsed.street_type)
        if parsed.city:
            parts.append(parsed.city)
        if parsed.state:
            parts.append(parsed.state)
        if parsed.zip_code:
            parts.append(parsed.zip_code)

        return " ".join(parts)

    async def count(self) -> int:
        """Get count of indexed addresses."""
        if not self.available:
            return 0

        try:
            if not await self.client.indices.exists(index=self.index_name):
                return 0
            result = await self.client.count(index=self.index_name)
            return result["count"]
        except Exception:
            return 0

    def stats(self) -> dict[str, Any]:
        """Return index statistics."""
        return {
            "available": self.available,
            "index_name": self.index_name,
            "is_serverless": self.is_serverless,
        }
