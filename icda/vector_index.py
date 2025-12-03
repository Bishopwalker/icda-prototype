from enum import Enum

import boto3
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection, AWSV4SignerAsyncAuth

from .embeddings import EmbeddingClient


class RouteType(str, Enum):
    CACHE_HIT = "cache"
    DATABASE = "database"
    NOVA = "nova"


class VectorIndex:
    __slots__ = ("client", "index", "available", "embedder")

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

    def __init__(self, embedder: EmbeddingClient, index: str):
        self.client: AsyncOpenSearch | None = None
        self.index = index
        self.available = False
        self.embedder = embedder

    async def connect(self, host: str, region: str) -> None:
        if not host:
            print("OpenSearch host not configured, router will use keyword matching")
            return
        try:
            credentials = boto3.Session().get_credentials()
            service = "aoss" if "aoss.amazonaws.com" in host else "es"
            self.client = AsyncOpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=AWSV4SignerAsyncAuth(credentials, region, service),
                use_ssl=True, verify_certs=True, connection_class=AsyncHttpConnection
            )
            await self.client.info()
            self.available = True
            print(f"OpenSearch connected: {host}")
            await self._ensure_index()
        except Exception as e:
            print(f"OpenSearch unavailable: {e}")

    async def _ensure_index(self) -> None:
        if not await self.client.indices.exists(index=self.index):
            await self.client.indices.create(index=self.index, body=self.INDEX_MAPPING)
            await self._seed_routing_data()
            print(f"Created vector index: {self.index}")

    async def _seed_routing_data(self) -> None:
        routing_docs = [
            {"text": "look up customer by CRID", "type": "endpoint", "route": "database", "metadata": {"tool": "lookup_crid"}},
            {"text": "find customer record ID", "type": "endpoint", "route": "database", "metadata": {"tool": "lookup_crid"}},
            {"text": "search customers by state", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "customers in Nevada California Texas", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "customers who moved twice three times", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "high movers frequent movers", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "customer statistics count by state", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "how many customers total", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "analyze trends patterns", "type": "document", "route": "nova", "metadata": {}},
            {"text": "explain why customers moving", "type": "document", "route": "nova", "metadata": {}},
            {"text": "compare summarize insights", "type": "document", "route": "nova", "metadata": {}},
            {"text": "recommend suggest predict", "type": "document", "route": "nova", "metadata": {}},
        ]
        for doc in routing_docs:
            doc["embedding"] = self.embedder.embed(doc["text"])
            await self.client.index(index=self.index, body=doc)
        await self.client.indices.refresh(index=self.index)

    async def close(self) -> None:
        if self.client:
            await self.client.close()

    async def find_route(self, query: str, k: int = 3) -> tuple[RouteType, dict]:
        if not self.available:
            return self._keyword_route(query)

        embedding = self.embedder.embed(query)
        if not embedding:
            return self._keyword_route(query)

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

    def _keyword_route(self, query: str) -> tuple[RouteType, dict]:
        q = query.casefold()
        if any(kw in q for kw in ("crid", "look up", "lookup", "find customer")):
            return RouteType.DATABASE, {"tool": "lookup_crid"}
        if any(kw in q for kw in ("search", "customers in", "state", "moved", "movers")):
            return RouteType.DATABASE, {"tool": "search_customers"}
        if any(kw in q for kw in ("how many", "count", "stats", "statistics")):
            return RouteType.DATABASE, {"tool": "get_stats"}
        return RouteType.NOVA, {}
