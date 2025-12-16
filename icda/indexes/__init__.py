"""
ICDA Index Management Package.

Provides a unified index hierarchy for RAG with federated search capabilities.

Index Architecture:
    - MasterIndex: Router/summary index for query routing
    - CodeIndex: Development context (code, APIs, dev docs)
    - KnowledgeIndex: User-facing RAG (guides, FAQs, procedures)
    - CustomersIndex: Customer data with address search

Also includes existing address verification indexes:
    - ZipDatabase: ZIP code lookup and validation
    - AddressVectorIndex: Address semantic search
"""

# Existing exports (address verification)
from .zip_database import ZipDatabase
from .address_vector_index import AddressVectorIndex

# New index hierarchy exports
from .base_index import BaseIndex, IndexConfig, IndexStats, SearchResult

__all__ = [
    # Existing
    "ZipDatabase",
    "AddressVectorIndex",
    # Base
    "BaseIndex",
    "IndexConfig",
    "IndexStats",
    "SearchResult",
]


# Lazy imports to avoid circular dependencies
def __getattr__(name: str):
    """Lazy load index classes to avoid import cycles."""
    if name == "MasterIndex":
        from .master_index import MasterIndex
        return MasterIndex
    elif name == "CodeIndex":
        from .code_index import CodeIndex
        return CodeIndex
    elif name == "KnowledgeIndex":
        from .knowledge_index import KnowledgeIndex
        return KnowledgeIndex
    elif name == "CustomersIndex":
        from .customers_index import CustomersIndex
        return CustomersIndex
    elif name == "IndexFederation":
        from .index_federation import IndexFederation
        return IndexFederation
    elif name == "DeduplicationManager":
        from .deduplication import DeduplicationManager
        return DeduplicationManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
