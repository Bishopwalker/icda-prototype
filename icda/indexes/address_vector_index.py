"""Vector index for semantic address search.

Uses OpenSearch kNN for semantic similarity matching of addresses.
Falls back gracefully if OpenSearch is not available.
"""

import logging
import os
from typing import Any

from icda.address_models import ParsedAddress

logger = logging.getLogger(__name__)

# Optional imports
try:
    from opensearchpy import AsyncOpenSearch, AsyncHttpConnection, AWSV4SignerAsyncAuth
    OPENSEARCH_AVAILABLE = True
except ImportError:
    OPENSEARCH_AVAILABLE = False

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class AddressVectorIndex:
    """Vector-based semantic address search using OpenSearch.

    Gracefully disabled if OpenSearch is not available.
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

    def __init__(self, embedder, index_name: str = "icda-addresses"):
        self.embedder = embedder
        self.index_name = index_name
        self.client = None
        self.available = False
        self.is_serverless = False

    async def connect(self, host: str, region: str) -> bool:
        """Connect to OpenSearch."""
        if not host:
            logger.info("AddressVectorIndex: No host configured")
            return False

        if not OPENSEARCH_AVAILABLE:
            logger.info("AddressVectorIndex: opensearch-py not installed")
            return False

        self.is_serverless = "aoss.amazonaws.com" in host
        is_aws = "amazonaws.com" in host

        try:
            if is_aws:
                if not BOTO3_AVAILABLE:
                    logger.info("AddressVectorIndex: boto3 not installed")
                    return False

                # Use default credential chain (supports env vars, profile, IAM role, SSO, etc.)
                credentials = boto3.Session().get_credentials()
                if not credentials:
                    logger.info("AddressVectorIndex: No AWS credentials")
                    return False
                    
                service = "aoss" if self.is_serverless else "es"
                self.client = AsyncOpenSearch(
                    hosts=[{"host": host, "port": 443}],
                    http_auth=AWSV4SignerAsyncAuth(credentials, region, service),
                    use_ssl=True, verify_certs=True, connection_class=AsyncHttpConnection,
                )
            else:
                self.client = AsyncOpenSearch(
                    hosts=[host], use_ssl=False, verify_certs=False, connection_class=AsyncHttpConnection,
                )

            if self.is_serverless:
                await self.client.indices.get_alias()
            else:
                await self.client.info()

            self.available = True
            await self._ensure_index()
            return True

        except Exception as e:
            logger.warning(f"AddressVectorIndex: Connection failed - {e}")
            self.available = False
            return False

    async def _ensure_index(self) -> None:
        if not self.client:
            return
        try:
            if not await self.client.indices.exists(index=self.index_name):
                await self.client.indices.create(index=self.index_name, body=self.INDEX_MAPPING)
        except Exception as e:
            logger.error(f"Failed to create address index: {e}")

    async def close(self) -> None:
        if self.client:
            await self.client.close()
            self.client = None
            self.available = False

    async def index_address(self, parsed: ParsedAddress, customer_id: str) -> bool:
        if not self.available:
            return False

        address_text = self._create_address_text(parsed)
        embedding = self.embedder.embed(address_text) if self.embedder else None
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
        self, query: str, limit: int = 10, state_filter: str = None, zip_filter: str = None
    ) -> list[dict[str, Any]]:
        if not self.available or not self.embedder:
            return []

        embedding = self.embedder.embed(query)
        if not embedding:
            return []

        must_clauses = []
        if state_filter:
            must_clauses.append({"term": {"state": state_filter.upper()}})
        if zip_filter:
            must_clauses.append({"term": {"zip_code": zip_filter}})

        if must_clauses:
            search_body = {
                "size": limit,
                "query": {"bool": {"must": must_clauses, "should": [{"knn": {"embedding": {"vector": embedding, "k": limit * 2}}}]}}
            }
        else:
            search_body = {"size": limit, "query": {"knn": {"embedding": {"vector": embedding, "k": limit}}}}

        try:
            resp = await self.client.search(index=self.index_name, body=search_body)
            return [
                {
                    "address_text": h["_source"].get("address_text"),
                    "street_number": h["_source"].get("street_number"),
                    "street_name": h["_source"].get("street_name"),
                    "street_type": h["_source"].get("street_type"),
                    "city": h["_source"].get("city"),
                    "state": h["_source"].get("state"),
                    "zip_code": h["_source"].get("zip_code"),
                    "customer_id": h["_source"].get("customer_id"),
                    "score": round(h["_score"], 4),
                }
                for h in resp["hits"]["hits"]
            ]
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def search_multi_state(self, query: str, states: list[str], limit_per_state: int = 5) -> dict[str, list[dict[str, Any]]]:
        results = {}
        for state in states:
            state_results = await self.search_semantic(query, limit=limit_per_state, state_filter=state)
            if state_results:
                results[state] = state_results
        return results

    def _create_address_text(self, parsed: ParsedAddress) -> str:
        parts = [parsed.street_number, parsed.street_name, parsed.street_type, parsed.city, parsed.state, parsed.zip_code]
        return " ".join(p for p in parts if p)

    async def count(self) -> int:
        if not self.available:
            return 0
        try:
            if not await self.client.indices.exists(index=self.index_name):
                return 0
            return (await self.client.count(index=self.index_name))["count"]
        except Exception:
            return 0

    def stats(self) -> dict[str, Any]:
        return {"available": self.available, "index_name": self.index_name, "is_serverless": self.is_serverless}
