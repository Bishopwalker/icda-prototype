"""Vector index with OpenSearch or keyword fallback.

Works in LITE MODE (no OpenSearch) with automatic keyword-based routing.
"""

import os
from enum import Enum
from typing import Callable

# Optional imports - gracefully handle missing packages
try:
    from opensearchpy import AsyncOpenSearch, AsyncHttpConnection, AWSV4SignerAsyncAuth, helpers
    OPENSEARCH_AVAILABLE = True
except ImportError:
    OPENSEARCH_AVAILABLE = False
    AsyncOpenSearch = None

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None


class RouteType(str, Enum):
    CACHE_HIT = "cache"
    DATABASE = "database"
    NOVA = "nova"


class VectorIndex:
    """Vector search with OpenSearch or keyword fallback."""
    
    __slots__ = ("client", "index", "customer_index", "available", "embedder", "host", "region", "is_serverless")

    INDEX_MAPPING = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "text": {"type": "text"},
                "type": {"type": "keyword"},
                "route": {"type": "keyword"},
                "metadata": {"type": "object"},
                "embedding": {"type": "knn_vector", "dimension": 1024, "method": {
                    "name": "hnsw", "space_type": "cosinesimil", "engine": "nmslib"
                }}
            }
        }
    }

    CUSTOMER_INDEX_MAPPING = {
        "settings": {"index": {"knn": True, "number_of_shards": 2, "number_of_replicas": 1}},
        "mappings": {
            "properties": {
                "crid": {"type": "keyword"},
                "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "address": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "city": {"type": "keyword"},
                "state": {"type": "keyword"},
                "zip": {"type": "keyword"},
                "customer_type": {"type": "keyword"},
                "status": {"type": "keyword"},
                "move_count": {"type": "integer"},
                "last_move": {"type": "date", "format": "yyyy-MM-dd", "null_value": "1970-01-01"},
                "created_date": {"type": "date", "format": "yyyy-MM-dd"},
                "search_text": {"type": "text"},
                "embedding": {"type": "knn_vector", "dimension": 1024, "method": {
                    "name": "hnsw", "space_type": "cosinesimil", "engine": "nmslib",
                    "parameters": {"ef_construction": 256, "m": 48}
                }}
            }
        }
    }

    def __init__(self, embedder, index: str):
        self.client = None
        self.index = index
        self.customer_index = f"{index}-customers"
        self.available = False
        self.embedder = embedder
        self.host = ""
        self.region = ""
        self.is_serverless = False

    async def connect(self, host: str, region: str) -> None:
        """Connect to OpenSearch or fall back to keyword routing."""
        if not host:
            print("VectorIndex: No OpenSearch host - using keyword routing")
            return
            
        if not OPENSEARCH_AVAILABLE:
            print("VectorIndex: opensearch-py not installed - using keyword routing")
            return

        self.host = host
        self.region = region
        self.is_serverless = "aoss.amazonaws.com" in host
        is_aws = "amazonaws.com" in host

        try:
            print(f"VectorIndex: Connecting to {host}")
            
            if is_aws:
                if not BOTO3_AVAILABLE:
                    print("VectorIndex: boto3 not installed - using keyword routing")
                    return
                    
                credentials = boto3.Session().get_credentials()
                if not credentials:
                    print("VectorIndex: No AWS credentials - using keyword routing")
                    return
                    
                service = "aoss" if self.is_serverless else "es"
                self.client = AsyncOpenSearch(
                    hosts=[{"host": host, "port": 443}],
                    http_auth=AWSV4SignerAsyncAuth(credentials, region, service),
                    use_ssl=True, verify_certs=True, connection_class=AsyncHttpConnection
                )
            else:
                connection_host = host.replace("localhost", "127.0.0.1")
                self.client = AsyncOpenSearch(
                    hosts=[connection_host],
                    use_ssl=False,
                    verify_certs=False,
                    connection_class=AsyncHttpConnection
                )

            if self.is_serverless:
                await self.client.indices.get_alias()
            else:
                await self.client.info()
            self.available = True
            print(f"VectorIndex: Connected to OpenSearch")
            await self._ensure_index()
        except Exception as e:
            print(f"VectorIndex: Connection failed ({e}) - using keyword routing")

    async def _ensure_index(self) -> None:
        if not await self.client.indices.exists(index=self.index):
            await self.client.indices.create(index=self.index, body=self.INDEX_MAPPING)
            await self._seed_routing_data()
            print(f"  Created routing index: {self.index}")

    async def _seed_routing_data(self) -> None:
        """Seed routing patterns for query classification."""
        routing_docs = [
            {"text": "look up customer by CRID", "type": "endpoint", "route": "database", "metadata": {"tool": "lookup_crid"}},
            {"text": "find customer record ID", "type": "endpoint", "route": "database", "metadata": {"tool": "lookup_crid"}},
            {"text": "search customers by state", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "customers in Nevada California Texas", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "customer statistics count by state", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "how many customers total", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "analyze trends patterns", "type": "document", "route": "nova", "metadata": {}},
            {"text": "explain why customers moving", "type": "document", "route": "nova", "metadata": {}},
        ]
        
        for doc in routing_docs:
            if self.embedder and self.embedder.available:
                doc["embedding"] = self.embedder.embed(doc["text"])
            await self.client.index(index=self.index, body=doc)
        await self.client.indices.refresh(index=self.index)

    async def close(self) -> None:
        if self.client:
            await self.client.close()

    async def find_route(self, query: str, k: int = 3) -> tuple[RouteType, dict]:
        """Route query to appropriate handler."""
        if not self.available:
            return self._keyword_route(query)

        if not self.embedder or not self.embedder.available:
            return self._keyword_route(query)

        embedding = self.embedder.embed(query)
        if not embedding:
            return self._keyword_route(query)

        try:
            resp = await self.client.search(
                index=self.index,
                body={"size": k, "query": {"knn": {"embedding": {"vector": embedding, "k": k}}}}
            )
            hits = resp["hits"]["hits"]
            if not hits:
                return RouteType.NOVA, {}

            routes = [h["_source"]["route"] for h in hits]
            best_route = max(set(routes), key=routes.count)
            metadata = hits[0]["_source"].get("metadata", {})
            return RouteType.DATABASE if best_route == "database" else RouteType.NOVA, metadata
        except Exception as e:
            print(f"VectorIndex: Route search failed ({e}) - using keyword routing")
            return self._keyword_route(query)

    def _keyword_route(self, query: str) -> tuple[RouteType, dict]:
        """Fallback keyword-based routing."""
        q = query.casefold()

        lookup_keywords = ("crid", "look up", "lookup", "find customer", "get customer", "customer record")
        if any(kw in q for kw in lookup_keywords):
            return RouteType.DATABASE, {"tool": "lookup_crid"}

        stats_keywords = ("how many", "count", "stats", "statistics", "total", "breakdown", "per state")
        if any(kw in q for kw in stats_keywords):
            return RouteType.DATABASE, {"tool": "get_stats"}

        search_keywords = ("search", "customers in", "state", "moved", "movers", "relocated", "residents")
        if any(kw in q for kw in search_keywords):
            return RouteType.DATABASE, {"tool": "search_customers"}

        return RouteType.NOVA, {}

    # Customer indexing methods
    async def ensure_customer_index(self) -> bool:
        if not self.available:
            return False
        try:
            if not await self.client.indices.exists(index=self.customer_index):
                await self.client.indices.create(index=self.customer_index, body=self.CUSTOMER_INDEX_MAPPING)
            return True
        except Exception:
            return False

    async def customer_count(self) -> int:
        if not self.available:
            return 0
        try:
            if not await self.client.indices.exists(index=self.customer_index):
                return 0
            result = await self.client.count(index=self.customer_index)
            return result["count"]
        except Exception:
            return 0

    async def search_customers_semantic(self, query: str, limit: int = 10, filters: dict = None) -> dict:
        """Semantic search for customers."""
        if not self.available:
            return {"success": False, "error": "OpenSearch not available - use /api/autocomplete instead", "count": 0, "data": []}

        if not self.embedder or not self.embedder.available:
            return {"success": False, "error": "Embeddings not available - use /api/autocomplete instead", "count": 0, "data": []}

        embedding = self.embedder.embed(query)
        if not embedding:
            return {"success": False, "error": "Failed to generate embedding", "count": 0, "data": []}

        must_clauses = []
        if filters:
            if filters.get("state"):
                must_clauses.append({"term": {"state": filters["state"].upper()}})
            if filters.get("city"):
                must_clauses.append({"match": {"city": filters["city"]}})
            if filters.get("min_moves"):
                must_clauses.append({"range": {"move_count": {"gte": filters["min_moves"]}}})

        if must_clauses:
            search_body = {
                "size": limit,
                "query": {"bool": {"must": must_clauses, "should": [{"knn": {"embedding": {"vector": embedding, "k": limit * 2}}}]}}
            }
        else:
            search_body = {"size": limit, "query": {"knn": {"embedding": {"vector": embedding, "k": limit}}}}

        try:
            resp = await self.client.search(index=self.customer_index, body=search_body)
            results = []
            for hit in resp["hits"]["hits"]:
                src = hit["_source"]
                results.append({
                    "crid": src["crid"], "name": src["name"], "address": src["address"],
                    "city": src["city"], "state": src["state"], "zip": src["zip"],
                    "customer_type": src["customer_type"], "status": src["status"],
                    "move_count": src["move_count"], "score": round(hit["_score"], 4)
                })
            return {"success": True, "query": query, "count": len(results), "data": results}
        except Exception as e:
            return {"success": False, "error": str(e), "count": 0, "data": []}

    async def search_customers_hybrid(self, query: str, limit: int = 10, filters: dict = None) -> dict:
        """Hybrid text + semantic search."""
        if not self.available:
            return {"success": False, "error": "OpenSearch not available", "count": 0, "data": []}

        embedding = self.embedder.embed(query) if self.embedder and self.embedder.available else None

        filter_clauses = []
        if filters:
            if filters.get("state"):
                filter_clauses.append({"term": {"state": filters["state"].upper()}})
            if filters.get("min_moves"):
                filter_clauses.append({"range": {"move_count": {"gte": filters["min_moves"]}}})

        search_body = {
            "size": limit,
            "query": {
                "bool": {
                    "should": [
                        {"multi_match": {"query": query, "fields": ["name^2", "address^3", "city^2", "search_text"], "type": "best_fields", "fuzziness": "AUTO"}}
                    ],
                    "filter": filter_clauses if filter_clauses else None
                }
            }
        }

        if embedding:
            search_body["query"]["bool"]["should"].append({"knn": {"embedding": {"vector": embedding, "k": limit}}})

        if not filter_clauses:
            del search_body["query"]["bool"]["filter"]

        try:
            resp = await self.client.search(index=self.customer_index, body=search_body)
            results = []
            for hit in resp["hits"]["hits"]:
                src = hit["_source"]
                results.append({
                    "crid": src["crid"], "name": src["name"], "address": src["address"],
                    "city": src["city"], "state": src["state"], "move_count": src["move_count"],
                    "score": round(hit["_score"], 4)
                })
            return {"success": True, "query": query, "count": len(results), "data": results}
        except Exception as e:
            return {"success": False, "error": str(e), "count": 0, "data": []}
