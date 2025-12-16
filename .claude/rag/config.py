"""
Universal RAG Configuration System
Manages environment variables and configuration for RAG, Memory, and Vector Storage
Domain-agnostic configuration that works with any project
"""

import os
from typing import Optional, Literal
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

VectorProviderType = Literal["chroma", "supabase"]


@dataclass
class RAGConfig:
    """
    Configuration for the RAG system with Mem0 and vector storage

    Environment Variables:
        VECTOR_PROVIDER: Which vector database to use (default: "chroma")
                        Options: "chroma" (local, free) or "supabase" (cloud)

        CHROMA_PERSIST_DIR: Directory for ChromaDB storage (default: "./.claude/rag/chroma_db")

        SUPABASE_URL: Supabase project URL (required if VECTOR_PROVIDER=supabase)
        SUPABASE_KEY: Supabase API key (required if VECTOR_PROVIDER=supabase)
        SUPABASE_TABLE: Table name for vector storage (default: "code_chunks")
        COLLECTION_NAME: Alternative name for collection/table (overrides SUPABASE_TABLE)

        MEM0_API_KEY: Mem0 API key (optional - uses local Mem0 if not provided)
        MEM0_ORGANIZATION_ID: Mem0 organization ID (optional for cloud Mem0)
        MEM0_PROJECT_ID: Mem0 project ID (optional for cloud Mem0)
        MEM0_MODE: "local" or "cloud" (default: "local" if no API key, else "cloud")

        EMBEDDING_MODEL: Sentence transformer model (default: "all-MiniLM-L6-v2")

    Example .env file:
        # Local setup (ChromaDB + Local Mem0) - Works out of the box!
        VECTOR_PROVIDER=chroma
        CHROMA_PERSIST_DIR=./.claude/rag/chroma_db
        MEM0_MODE=local

        # Cloud setup (Supabase + Cloud Mem0) - Optional enhancement
        VECTOR_PROVIDER=supabase
        SUPABASE_URL=https://xxxxx.supabase.co
        SUPABASE_KEY=your-supabase-anon-key
        SUPABASE_TABLE=code_chunks
        COLLECTION_NAME=my_project_code_chunks  # Optional: customize collection name
        MEM0_API_KEY=your-mem0-api-key
        MEM0_ORGANIZATION_ID=your-org-id
        MEM0_PROJECT_ID=your-project-id
        MEM0_MODE=cloud
    """

    # Vector Storage Configuration
    vector_provider: VectorProviderType
    chroma_persist_dir: str
    supabase_url: Optional[str]
    supabase_key: Optional[str]
    supabase_table: str

    # Mem0 Configuration
    mem0_api_key: Optional[str]
    mem0_organization_id: Optional[str]
    mem0_project_id: Optional[str]
    mem0_mode: Literal["local", "cloud"]

    # Model Configuration
    embedding_model: str

    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate_vector_config()
        self._validate_mem0_config()

    def _validate_vector_config(self):
        """Validate vector database configuration"""
        if self.vector_provider == "supabase":
            if not self.supabase_url:
                raise ValueError(
                    "SUPABASE_URL is required when VECTOR_PROVIDER=supabase. "
                    "Set it in your .env file or environment variables."
                )
            if not self.supabase_key:
                raise ValueError(
                    "SUPABASE_KEY is required when VECTOR_PROVIDER=supabase. "
                    "Set it in your .env file or environment variables."
                )

    def _validate_mem0_config(self):
        """Validate Mem0 configuration"""
        if self.mem0_mode == "cloud":
            if not self.mem0_api_key:
                raise ValueError(
                    "MEM0_API_KEY is required when MEM0_MODE=cloud. "
                    "Either provide the API key or set MEM0_MODE=local"
                )

    @property
    def is_using_cloud_vector(self) -> bool:
        """Check if using cloud vector storage"""
        return self.vector_provider == "supabase"

    @property
    def is_using_cloud_memory(self) -> bool:
        """Check if using cloud memory storage"""
        return self.mem0_mode == "cloud" and self.mem0_api_key is not None

    def get_vector_config(self) -> dict:
        """Get configuration dict for vector database initialization"""
        if self.vector_provider == "chroma":
            return {
                "persist_directory": self.chroma_persist_dir,
                "embedding_model": self.embedding_model
            }
        elif self.vector_provider == "supabase":
            return {
                "supabase_url": self.supabase_url,
                "supabase_key": self.supabase_key,
                "table_name": self.supabase_table,
                "embedding_model": self.embedding_model
            }
        else:
            raise ValueError(f"Unknown vector provider: {self.vector_provider}")

    def get_mem0_config(self) -> dict:
        """Get configuration dict for Mem0 initialization"""
        if self.mem0_mode == "local":
            return {"mode": "local"}
        else:
            config = {
                "mode": "cloud",
                "api_key": self.mem0_api_key
            }
            if self.mem0_organization_id:
                config["organization_id"] = self.mem0_organization_id
            if self.mem0_project_id:
                config["project_id"] = self.mem0_project_id
            return config


def load_config() -> RAGConfig:
    """
    Load configuration from environment variables with sensible defaults

    Returns:
        RAGConfig: Validated configuration object

    Raises:
        ValueError: If required configuration is missing

    Example:
        >>> config = load_config()
        >>> print(f"Using {config.vector_provider} for vector storage")
        >>> print(f"Using {config.mem0_mode} Mem0")
    """
    # Vector storage config
    vector_provider = os.getenv("VECTOR_PROVIDER", "chroma").lower()
    if vector_provider not in ["chroma", "supabase"]:
        raise ValueError(f"Invalid VECTOR_PROVIDER: {vector_provider}. Must be 'chroma' or 'supabase'")

    chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./.claude/rag/chroma_db")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    # Collection/table name - can be customized via COLLECTION_NAME or SUPABASE_TABLE
    collection_name = os.getenv("COLLECTION_NAME", os.getenv("SUPABASE_TABLE", "code_chunks"))
    supabase_table = collection_name

    # Mem0 config
    mem0_api_key = os.getenv("MEM0_API_KEY")
    mem0_organization_id = os.getenv("MEM0_ORGANIZATION_ID")
    mem0_project_id = os.getenv("MEM0_PROJECT_ID")

    # Auto-detect Mem0 mode based on API key presence
    mem0_mode = os.getenv("MEM0_MODE", "cloud" if mem0_api_key else "local").lower()
    if mem0_mode not in ["local", "cloud"]:
        raise ValueError(f"Invalid MEM0_MODE: {mem0_mode}. Must be 'local' or 'cloud'")

    # Model config
    embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    return RAGConfig(
        vector_provider=vector_provider,
        chroma_persist_dir=chroma_persist_dir,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        supabase_table=supabase_table,
        mem0_api_key=mem0_api_key,
        mem0_organization_id=mem0_organization_id,
        mem0_project_id=mem0_project_id,
        mem0_mode=mem0_mode,
        embedding_model=embedding_model
    )


def print_config_summary(config: RAGConfig):
    """
    Print a human-readable summary of the current configuration

    Args:
        config: RAGConfig object to summarize
    """
    print("=" * 60)
    print("Universal RAG System Configuration")
    print("=" * 60)
    print(f"Vector Storage: {config.vector_provider.upper()}")
    if config.vector_provider == "chroma":
        print(f"  - Persist Directory: {config.chroma_persist_dir}")
    else:
        print(f"  - Supabase URL: {config.supabase_url}")
        print(f"  - Table: {config.supabase_table}")

    print(f"\nMemory System: Mem0 ({config.mem0_mode.upper()})")
    if config.mem0_mode == "cloud":
        print(f"  - API Key: {'✓ Configured' if config.mem0_api_key else '✗ Missing'}")
        print(f"  - Organization ID: {config.mem0_organization_id or 'Not set'}")
        print(f"  - Project ID: {config.mem0_project_id or 'Not set'}")
    else:
        print(f"  - Mode: Local (no API key required)")

    print(f"\nEmbedding Model: {config.embedding_model}")
    print("=" * 60)


if __name__ == "__main__":
    # Test configuration loading
    try:
        config = load_config()
        print_config_summary(config)
        print("\n✓ Configuration loaded successfully!")
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        print("\nPlease check your .env file or environment variables.")
