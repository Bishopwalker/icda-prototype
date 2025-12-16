"""
Customers Index - Unified Customer Data Index.

Combines customer records with address search capabilities.
Supports both structured lookups and semantic search.

Features:
- Customer profile storage
- Address normalization and search
- Move history tracking
- Semantic customer search
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import logging

from .base_index import BaseIndex, IndexConfig, SearchResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CustomerRecord:
    """A customer record to be indexed."""
    crid: str
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    customer_type: str = "residential"
    status: str = "active"
    move_count: int = 0
    last_move: Optional[str] = None
    created_date: Optional[str] = None
    address_normalized: str = ""
    search_text: str = ""


class CustomersIndex(BaseIndex):
    """
    Customer index with address search capabilities.

    Combines functionality from previous vector_index and address_vector_index.
    Supports both CRID lookups and semantic customer search.

    Schema:
        - crid: Customer ID (primary key)
        - name: Customer name
        - address, city, state, zip: Address components
        - customer_type: Type (residential, commercial, etc.)
        - status: Account status
        - move_count: Number of moves
        - last_move, created_date: Timestamps
        - address_normalized: Normalized address for matching
        - search_text: Combined searchable text
        - embedding: Customer profile embedding
        - address_embedding: Separate address embedding
    """

    def __init__(
        self,
        opensearch_client: Any,
        embedder: Any,
        index_name: str = "icda-customers",
    ):
        config = IndexConfig(
            name=index_name,
            shards=2,
            replicas=0,
            max_result_window=50000,
        )
        super().__init__(opensearch_client, embedder, config)

    @property
    def mapping(self) -> dict[str, Any]:
        """OpenSearch mapping for the customers index."""
        return {
            "properties": {
                "crid": {"type": "keyword"},
                "name": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}},
                },
                "address": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}},
                },
                "city": {"type": "keyword"},
                "state": {"type": "keyword"},
                "zip": {"type": "keyword"},
                "customer_type": {"type": "keyword"},
                "status": {"type": "keyword"},
                "move_count": {"type": "integer"},
                "last_move": {"type": "date", "format": "yyyy-MM-dd||epoch_millis"},
                "created_date": {"type": "date", "format": "yyyy-MM-dd||epoch_millis"},
                "address_normalized": {"type": "text"},
                "search_text": {"type": "text"},
                "indexed_at": {"type": "date"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": self.EMBEDDING_DIMENSION,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                        "parameters": {
                            "ef_construction": 256,
                            "m": 48,
                        },
                    },
                },
                "address_embedding": {
                    "type": "knn_vector",
                    "dimension": self.EMBEDDING_DIMENSION,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
            }
        }

    async def index_customer(
        self,
        customer: CustomerRecord,
        generate_embeddings: bool = True,
    ) -> bool:
        """
        Index a customer record.

        Args:
            customer: CustomerRecord to index
            generate_embeddings: Whether to generate embeddings

        Returns:
            bool: True if indexed successfully
        """
        # Build search text
        search_text = customer.search_text or self._build_search_text(customer)

        # Normalize address
        address_normalized = customer.address_normalized or self._normalize_address(
            customer.address, customer.city, customer.state, customer.zip_code
        )

        document = {
            "crid": customer.crid,
            "name": customer.name,
            "address": customer.address,
            "city": customer.city,
            "state": customer.state,
            "zip": customer.zip_code,
            "customer_type": customer.customer_type,
            "status": customer.status,
            "move_count": customer.move_count,
            "last_move": customer.last_move,
            "created_date": customer.created_date,
            "address_normalized": address_normalized,
            "search_text": search_text,
            "indexed_at": datetime.utcnow().isoformat(),
        }

        # Generate embeddings
        if generate_embeddings:
            # Profile embedding (for general customer search)
            profile_text = f"{customer.name} {customer.city} {customer.state} {customer.customer_type}"
            embedding = await self.generate_embedding(profile_text)
            if embedding:
                document["embedding"] = embedding

            # Address embedding (for address matching)
            address_embed = await self.generate_embedding(address_normalized)
            if address_embed:
                document["address_embedding"] = address_embed

        return await self.index_document(customer.crid, document, refresh=True)

    async def bulk_index_customers(
        self,
        customers: list[CustomerRecord],
        batch_size: int = 500,
        generate_embeddings: bool = True,
    ) -> tuple[int, int]:
        """
        Bulk index multiple customers.

        Args:
            customers: List of CustomerRecord objects
            batch_size: Batch size for bulk operations
            generate_embeddings: Whether to generate embeddings

        Returns:
            tuple: (success_count, error_count)
        """
        total_success = 0
        total_errors = 0

        for i in range(0, len(customers), batch_size):
            batch = customers[i:i + batch_size]
            documents = []

            for customer in batch:
                search_text = self._build_search_text(customer)
                address_normalized = self._normalize_address(
                    customer.address, customer.city, customer.state, customer.zip_code
                )

                doc = {
                    "crid": customer.crid,
                    "name": customer.name,
                    "address": customer.address,
                    "city": customer.city,
                    "state": customer.state,
                    "zip": customer.zip_code,
                    "customer_type": customer.customer_type,
                    "status": customer.status,
                    "move_count": customer.move_count,
                    "last_move": customer.last_move,
                    "created_date": customer.created_date,
                    "address_normalized": address_normalized,
                    "search_text": search_text,
                    "indexed_at": datetime.utcnow().isoformat(),
                }

                if generate_embeddings:
                    profile_text = f"{customer.name} {customer.city} {customer.state}"
                    embedding = await self.generate_embedding(profile_text)
                    if embedding:
                        doc["embedding"] = embedding

                documents.append((customer.crid, doc))

            success, errors = await self.bulk_index(documents, refresh=False)
            total_success += success
            total_errors += errors

            logger.info(f"Indexed batch {i // batch_size + 1}: {success} success, {errors} errors")

        # Final refresh
        await self.refresh()

        return total_success, total_errors

    def _build_search_text(self, customer: CustomerRecord) -> str:
        """Build combined searchable text for a customer."""
        parts = [
            customer.crid,
            customer.name,
            customer.address,
            customer.city,
            customer.state,
            customer.zip_code,
            customer.customer_type,
            customer.status,
        ]
        return " ".join(str(p) for p in parts if p)

    def _normalize_address(
        self,
        address: str,
        city: str,
        state: str,
        zip_code: str,
    ) -> str:
        """Normalize an address for matching."""
        # Uppercase and clean
        parts = [
            address.upper().strip(),
            city.upper().strip(),
            state.upper().strip(),
            zip_code.strip(),
        ]
        normalized = " ".join(p for p in parts if p)

        # Common abbreviations
        replacements = {
            " STREET": " ST",
            " AVENUE": " AVE",
            " BOULEVARD": " BLVD",
            " DRIVE": " DR",
            " LANE": " LN",
            " ROAD": " RD",
            " COURT": " CT",
            " PLACE": " PL",
            " NORTH": " N",
            " SOUTH": " S",
            " EAST": " E",
            " WEST": " W",
        }

        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        return normalized

    async def lookup_crid(self, crid: str) -> Optional[dict[str, Any]]:
        """
        Look up a customer by CRID.

        Args:
            crid: Customer ID

        Returns:
            Customer document or None
        """
        return await self.get_document(crid)

    async def search_customers(
        self,
        query: str,
        state: Optional[str] = None,
        city: Optional[str] = None,
        customer_type: Optional[str] = None,
        status: Optional[str] = None,
        min_moves: Optional[int] = None,
        k: int = 10,
    ) -> list[SearchResult]:
        """
        Search for customers.

        Args:
            query: Search query (name, address, etc.)
            state: Filter by state
            city: Filter by city
            customer_type: Filter by customer type
            status: Filter by status
            min_moves: Minimum move count
            k: Number of results

        Returns:
            List of matching customers
        """
        # Build filters
        filters: list[dict[str, Any]] = []

        if state:
            filters.append({"term": {"state": state.upper()}})

        if city:
            filters.append({"term": {"city": city.upper()}})

        if customer_type:
            filters.append({"term": {"customer_type": customer_type}})

        if status:
            filters.append({"term": {"status": status}})

        if min_moves is not None:
            filters.append({"range": {"move_count": {"gte": min_moves}}})

        filter_query = {"bool": {"must": filters}} if filters else None

        # Try semantic search first
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
                    "should": [
                        {"match": {"search_text": {"query": query, "boost": 2.0}}},
                        {"match": {"name": {"query": query, "boost": 1.5}}},
                        {"match": {"address": query}},
                    ],
                    "minimum_should_match": 1,
                }
            }

            if filter_query:
                text_query["bool"]["filter"] = filter_query["bool"]["must"]

            return await self.search(text_query, size=k)

    async def search_by_address(
        self,
        address: str,
        k: int = 10,
        threshold: float = 0.7,
    ) -> list[SearchResult]:
        """
        Search for customers by address similarity.

        Uses the address_embedding field for semantic address matching.

        Args:
            address: Address to search for
            k: Number of results
            threshold: Minimum similarity score

        Returns:
            List of matching customers
        """
        # Normalize the search address
        normalized = self._normalize_address(address, "", "", "")

        # Generate address embedding
        embedding = await self.generate_embedding(normalized)

        if embedding:
            # Search using address_embedding field
            if not self.available:
                return []

            try:
                result = await self.client.search(
                    index=self.index_name,
                    body={
                        "query": {
                            "knn": {
                                "address_embedding": {
                                    "vector": embedding,
                                    "k": k,
                                }
                            }
                        },
                        "size": k,
                        "min_score": threshold,
                    },
                )

                hits = result.get("hits", {}).get("hits", [])
                return [
                    SearchResult(
                        doc_id=hit["_id"],
                        chunk_id=hit["_id"],
                        text=hit.get("_source", {}).get("address_normalized", ""),
                        score=hit.get("_score", 0.0),
                        source_index=self.index_name,
                        metadata=hit.get("_source", {}),
                    )
                    for hit in hits
                ]

            except Exception as e:
                logger.error(f"Address search failed: {e}")
                return []
        else:
            # Fallback to text matching
            query = {
                "match": {
                    "address_normalized": {
                        "query": normalized,
                        "fuzziness": "AUTO",
                    }
                }
            }
            return await self.search(query, size=k)

    async def get_customers_by_state(
        self,
        state: str,
        limit: int = 100,
    ) -> list[SearchResult]:
        """Get customers in a state."""
        query = {"term": {"state": state.upper()}}
        return await self.search(query, size=limit)

    async def get_high_movers(
        self,
        min_moves: int = 2,
        limit: int = 100,
    ) -> list[SearchResult]:
        """Get customers with high move counts."""
        query = {"range": {"move_count": {"gte": min_moves}}}
        return await self.search(query, size=limit)

    async def get_stats_by_state(self) -> dict[str, int]:
        """Get customer count by state."""
        if not self.available:
            return {}

        try:
            result = await self.client.search(
                index=self.index_name,
                body={
                    "size": 0,
                    "aggs": {
                        "by_state": {
                            "terms": {"field": "state", "size": 60}
                        }
                    },
                },
            )

            buckets = result.get("aggregations", {}).get("by_state", {}).get("buckets", [])
            return {b["key"]: b["doc_count"] for b in buckets}

        except Exception as e:
            logger.error(f"Failed to get stats by state: {e}")
            return {}
