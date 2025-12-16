"""
Adaptive RAG System - Kubernetes-like Auto-Configuration
Provides semantic search over any codebase using vector embeddings

Features:
- Auto-detect environment (Bedrock, Copilot, Docker, Claude Code)
- Self-contained ChromaDB (no external accounts)
- Multi-interface: REST API, STDIN, File injection
- FedRAMP compliant (air-gapped mode supported)
- Multi-language code chunking (Java/Spring, Python, TypeScript)

Usage:
    # As Python module
    from rag import AdaptiveRAGEngine
    engine = AdaptiveRAGEngine("/path/to/project")
    engine.index_project()
    results = engine.query("find authentication logic")

    # As Docker service
    docker-compose -f docker-compose.rag.yml up -d
    curl http://localhost:8080/query -d '{"query": "find auth"}'

    # As CLI
    python -m rag.adaptive_rag --project /path/to/project --serve
"""

from .chunking_strategy import (
    EBLChunkingStrategy,
    UniversalChunkingStrategy,
    CodeChunk,
    ChunkType
)
from .vector_database import (
    VectorProvider,
    BaseVectorDatabase,
    ChromaVectorDatabase,
    SupabaseVectorDatabase,
    VectorDatabaseFactory,
    CloudRAGPipeline
)
from .config import RAGConfig, load_config, print_config_summary
from .memory_service import MemoryService, MemoryType, Memory

# Adaptive RAG components
try:
    from .adaptive_rag import (
        AdaptiveRAGEngine,
        EnvironmentDetector,
        EnvironmentContext,
        InterfaceType,
        ProjectType,
        RESTAdapter,
        STDINAdapter,
        FileInjectAdapter,
    )
    _ADAPTIVE_AVAILABLE = True
except ImportError:
    _ADAPTIVE_AVAILABLE = False

__all__ = [
    # Adaptive RAG (main entry point)
    'AdaptiveRAGEngine',
    'EnvironmentDetector',
    'EnvironmentContext',
    'InterfaceType',
    'ProjectType',
    # Interface adapters
    'RESTAdapter',
    'STDINAdapter',
    'FileInjectAdapter',
    # Core RAG
    'UniversalChunkingStrategy',
    'EBLChunkingStrategy',  # Deprecated alias
    'CodeChunk',
    'ChunkType',
    'VectorProvider',
    'BaseVectorDatabase',
    'ChromaVectorDatabase',
    'SupabaseVectorDatabase',
    'VectorDatabaseFactory',
    'CloudRAGPipeline',
    # Configuration & Memory
    'RAGConfig',
    'load_config',
    'print_config_summary',
    'MemoryService',
    'MemoryType',
    'Memory'
]

__version__ = "2.0.0"
