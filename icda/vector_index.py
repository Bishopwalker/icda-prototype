from enum import Enum
from typing import Callable

import boto3
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection, AWSV4SignerAsyncAuth, helpers

from .embeddings import EmbeddingClient


class RouteType(str, Enum):
    CACHE_HIT = "cache"
    DATABASE = "database"
    NOVA = "nova"


class VectorIndex:
    __slots__ = ("client", "index", "customer_index", "available", "embedder", "host", "region", "is_serverless")

    # Routing index mapping (for query routing)
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

    # Customer index mapping (for semantic customer search)
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
                "search_text": {"type": "text"},  # Combined text for full-text search
                "embedding": {"type": "knn_vector", "dimension": 1024, "method": {
                    "name": "hnsw", "space_type": "cosinesimil", "engine": "nmslib",
                    "parameters": {"ef_construction": 256, "m": 48}
                }}
            }
        }
    }

    def __init__(self, embedder: EmbeddingClient, index: str):
        self.client: AsyncOpenSearch | None = None
        self.index = index
        self.customer_index = f"{index}-customers"
        self.available = False
        self.embedder = embedder
        self.host = ""
        self.region = ""

    async def connect(self, host: str, region: str) -> None:
        if not host:
            print("OpenSearch host not configured, router will use keyword matching")
            return
        self.host = host
        self.region = region
        self.is_serverless = "aoss.amazonaws.com" in host
        try:
            credentials = boto3.Session().get_credentials()
            service = "aoss" if self.is_serverless else "es"
            self.client = AsyncOpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=AWSV4SignerAsyncAuth(credentials, region, service),
                use_ssl=True, verify_certs=True, connection_class=AsyncHttpConnection
            )
            # Serverless doesn't support .info(), test with index list instead
            if self.is_serverless:
                await self.client.indices.get_alias()
            else:
                await self.client.info()
            self.available = True
            print(f"OpenSearch {'Serverless ' if self.is_serverless else ''}connected: {host}")
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
            # === LOOKUP queries (CRID/ID-based) ===
            {"text": "look up customer by CRID", "type": "endpoint", "route": "database", "metadata": {"tool": "lookup_crid"}},
            {"text": "find customer record ID", "type": "endpoint", "route": "database", "metadata": {"tool": "lookup_crid"}},
            {"text": "get customer details for CRID", "type": "endpoint", "route": "database", "metadata": {"tool": "lookup_crid"}},
            {"text": "show me customer info", "type": "endpoint", "route": "database", "metadata": {"tool": "lookup_crid"}},
            {"text": "what's the record for this customer", "type": "endpoint", "route": "database", "metadata": {"tool": "lookup_crid"}},
            {"text": "pull up that customer", "type": "endpoint", "route": "database", "metadata": {"tool": "lookup_crid"}},

            # === SEARCH queries (state, city, moves) ===
            {"text": "search customers by state", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "customers in Nevada California Texas", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "customers who moved twice three times", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "high movers frequent movers", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "give me all Nevada residents", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "list California customers", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "I want to see customers from TX", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "show customers in New York", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "people who relocated multiple times", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "customers who move a lot", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "find people in Las Vegas", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "customers living in Miami", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "who lives in Denver", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "customers from the west coast", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "show me relocators", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},
            {"text": "active customers in state", "type": "endpoint", "route": "database", "metadata": {"tool": "search_customers"}},

            # === STATS queries (counts, aggregations) ===
            {"text": "customer statistics count by state", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "how many customers total", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "states with most customers", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "which state has the most moves", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "customer numbers breakdown", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "give me the totals", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "overall customer count", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},
            {"text": "summary of customers per state", "type": "endpoint", "route": "database", "metadata": {"tool": "get_stats"}},

            # === NOVA queries (analysis, insights, recommendations) ===
            {"text": "analyze trends patterns", "type": "document", "route": "nova", "metadata": {}},
            {"text": "explain why customers moving", "type": "document", "route": "nova", "metadata": {}},
            {"text": "compare summarize insights", "type": "document", "route": "nova", "metadata": {}},
            {"text": "recommend suggest predict", "type": "document", "route": "nova", "metadata": {}},
            {"text": "predict which customers will move", "type": "document", "route": "nova", "metadata": {}},
            {"text": "analyze relocation trends", "type": "document", "route": "nova", "metadata": {}},
            {"text": "compare Nevada vs California", "type": "document", "route": "nova", "metadata": {}},
            {"text": "what are the migration patterns", "type": "document", "route": "nova", "metadata": {}},
            {"text": "why do people relocate so much", "type": "document", "route": "nova", "metadata": {}},
            {"text": "insights on customer behavior", "type": "document", "route": "nova", "metadata": {}},
            {"text": "which customers should we contact", "type": "document", "route": "nova", "metadata": {}},
            {"text": "tell me about the data", "type": "document", "route": "nova", "metadata": {}},
            {"text": "help me understand this", "type": "document", "route": "nova", "metadata": {}},
            {"text": "what does this mean", "type": "document", "route": "nova", "metadata": {}},
            {"text": "general question about customers", "type": "document", "route": "nova", "metadata": {}},
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
        """Fallback keyword-based routing when OpenSearch is unavailable."""
        q = query.casefold()

        # LOOKUP: CRID-based customer retrieval
        lookup_keywords = (
            "crid", "look up", "lookup", "find customer", "get customer",
            "show me customer", "pull up", "customer record", "customer details"
        )
        if any(kw in q for kw in lookup_keywords):
            return RouteType.DATABASE, {"tool": "lookup_crid"}

        # STATS: counts, totals, breakdowns
        stats_keywords = (
            "how many", "count", "stats", "statistics", "total", "totals",
            "breakdown", "numbers", "per state", "by state", "summary"
        )
        if any(kw in q for kw in stats_keywords):
            return RouteType.DATABASE, {"tool": "get_stats"}

        # SEARCH: state, city, location-based, movers
        search_keywords = (
            "search", "customers in", "state", "moved", "movers", "relocated",
            "residents", "living in", "from", "show", "list", "give me",
            "find people", "who lives", "customers from", "people in",
            "active", "frequent", "high movers", "relocators"
        )
        if any(kw in q for kw in search_keywords):
            return RouteType.DATABASE, {"tool": "search_customers"}

        # Default: Let Nova handle complex/ambiguous queries
        return RouteType.NOVA, {}

    # ==================== Customer Indexing Methods ====================

    async def ensure_customer_index(self) -> bool:
        """Create the customer index if it doesn't exist"""
        if not self.available:
            return False
        try:
            if not await self.client.indices.exists(index=self.customer_index):
                await self.client.indices.create(index=self.customer_index, body=self.CUSTOMER_INDEX_MAPPING)
                print(f"Created customer index: {self.customer_index}")
            return True
        except Exception as e:
            print(f"Failed to create customer index: {e}")
            return False

    async def delete_customer_index(self) -> bool:
        """Delete and recreate the customer index"""
        if not self.available:
            return False
        try:
            if await self.client.indices.exists(index=self.customer_index):
                await self.client.indices.delete(index=self.customer_index)
                print(f"Deleted customer index: {self.customer_index}")
            return True
        except Exception as e:
            print(f"Failed to delete customer index: {e}")
            return False

    async def index_customers(self, customers: list[dict], batch_size: int = 100,
                              progress_callback: Callable[[int, int], None] = None) -> dict:
        """
        Index customers into OpenSearch with embeddings.

        Args:
            customers: List of customer dicts from CustomerDB
            batch_size: Number of customers to process at a time
            progress_callback: Optional callback(indexed_count, total_count)

        Returns:
            dict with success status and counts
        """
        if not self.available:
            return {"success": False, "error": "OpenSearch not available"}

        await self.ensure_customer_index()

        total = len(customers)
        indexed = 0
        errors = 0

        for i in range(0, total, batch_size):
            batch = customers[i:i + batch_size]
            actions = []

            for customer in batch:
                # Create searchable text combining key fields
                search_text = f"{customer['name']} {customer['address']} {customer['city']} {customer['state']}"

                # Generate embedding for semantic search
                embedding = self.embedder.embed(search_text)
                if not embedding:
                    errors += 1
                    continue

                doc_source = {
                    "crid": customer["crid"],
                    "name": customer["name"],
                    "address": customer["address"],
                    "city": customer["city"],
                    "state": customer["state"],
                    "zip": customer["zip"],
                    "customer_type": customer["customer_type"],
                    "status": customer["status"],
                    "move_count": customer["move_count"],
                    "last_move": customer.get("last_move") or "1970-01-01",
                    "created_date": customer["created_date"],
                    "search_text": search_text,
                    "embedding": embedding
                }

                # Serverless doesn't support custom document IDs
                if self.is_serverless:
                    doc = {"_index": self.customer_index, "_source": doc_source}
                else:
                    doc = {"_index": self.customer_index, "_id": customer["crid"], "_source": doc_source}
                actions.append(doc)

            if actions:
                try:
                    success, failed = await helpers.async_bulk(self.client, actions, raise_on_error=False)
                    indexed += success
                    if failed:
                        errors += len(failed)
                        # Log first error for debugging
                        if failed and len(failed) > 0:
                            print(f"Bulk error sample: {failed[0]}")
                except Exception as e:
                    print(f"Bulk index error: {e}")
                    errors += len(actions)

            if progress_callback:
                progress_callback(indexed, total)

        # Refresh index to make documents searchable (not supported on Serverless)
        if not self.is_serverless:
            await self.client.indices.refresh(index=self.customer_index)

        return {
            "success": True,
            "indexed": indexed,
            "errors": errors,
            "total": total
        }

    async def customer_count(self) -> int:
        """Get count of indexed customers"""
        if not self.available:
            return 0
        try:
            if not await self.client.indices.exists(index=self.customer_index):
                return 0
            result = await self.client.count(index=self.customer_index)
            return result["count"]
        except Exception:
            return 0

    async def search_customers_semantic(self, query: str, limit: int = 10,
                                         filters: dict = None) -> dict:
        """
        Semantic search for customers using vector similarity.

        Args:
            query: Natural language query (e.g., "customers in Las Vegas who moved frequently")
            limit: Max results to return
            filters: Optional filters like {"state": "NV", "min_moves": 2}

        Returns:
            dict with matching customers and scores
        """
        if not self.available:
            return {"success": False, "error": "OpenSearch not available"}

        embedding = self.embedder.embed(query)
        if not embedding:
            return {"success": False, "error": "Failed to generate embedding"}

        # Build query with optional filters
        must_clauses = []
        if filters:
            if filters.get("state"):
                must_clauses.append({"term": {"state": filters["state"].upper()}})
            if filters.get("city"):
                must_clauses.append({"match": {"city": filters["city"]}})
            if filters.get("min_moves"):
                must_clauses.append({"range": {"move_count": {"gte": filters["min_moves"]}}})
            if filters.get("status"):
                must_clauses.append({"term": {"status": filters["status"].upper()}})
            if filters.get("customer_type"):
                must_clauses.append({"term": {"customer_type": filters["customer_type"].upper()}})

        # KNN query with filters
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
            resp = await self.client.search(index=self.customer_index, body=search_body)
            hits = resp["hits"]["hits"]

            results = []
            for hit in hits:
                source = hit["_source"]
                results.append({
                    "crid": source["crid"],
                    "name": source["name"],
                    "address": source["address"],
                    "city": source["city"],
                    "state": source["state"],
                    "zip": source["zip"],
                    "customer_type": source["customer_type"],
                    "status": source["status"],
                    "move_count": source["move_count"],
                    "score": round(hit["_score"], 4)
                })

            return {
                "success": True,
                "query": query,
                "count": len(results),
                "data": results
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_customers_hybrid(self, query: str, limit: int = 10,
                                       filters: dict = None) -> dict:
        """
        Hybrid search combining full-text and semantic search.
        Better for address autocomplete with typo tolerance.
        """
        if not self.available:
            return {"success": False, "error": "OpenSearch not available"}

        embedding = self.embedder.embed(query)

        # Build filter clauses
        filter_clauses = []
        if filters:
            if filters.get("state"):
                filter_clauses.append({"term": {"state": filters["state"].upper()}})
            if filters.get("min_moves"):
                filter_clauses.append({"range": {"move_count": {"gte": filters["min_moves"]}}})

        # Hybrid query: combine text match with KNN
        search_body = {
            "size": limit,
            "query": {
                "bool": {
                    "should": [
                        # Full-text search on combined fields
                        {"multi_match": {
                            "query": query,
                            "fields": ["name^2", "address^3", "city^2", "search_text"],
                            "type": "best_fields",
                            "fuzziness": "AUTO"
                        }},
                    ],
                    "filter": filter_clauses if filter_clauses else None
                }
            }
        }

        # Add KNN if embedding succeeded
        if embedding:
            search_body["query"]["bool"]["should"].append(
                {"knn": {"embedding": {"vector": embedding, "k": limit}}}
            )

        # Remove None filter
        if not filter_clauses:
            del search_body["query"]["bool"]["filter"]

        try:
            resp = await self.client.search(index=self.customer_index, body=search_body)
            hits = resp["hits"]["hits"]

            results = []
            for hit in hits:
                source = hit["_source"]
                results.append({
                    "crid": source["crid"],
                    "name": source["name"],
                    "address": source["address"],
                    "city": source["city"],
                    "state": source["state"],
                    "move_count": source["move_count"],
                    "score": round(hit["_score"], 4)
                })

            return {
                "success": True,
                "query": query,
                "count": len(results),
                "data": results
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
