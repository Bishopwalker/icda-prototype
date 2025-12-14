"""Configuration with sensible defaults for LITE MODE (no external services)."""

from dataclasses import dataclass, field
from os import getenv


@dataclass(slots=True, frozen=True)
class Config:
    # AWS (optional - empty = LITE MODE)
    aws_region: str = field(default_factory=lambda: getenv("AWS_REGION", "us-east-1"))
    nova_model: str = field(default_factory=lambda: getenv("NOVA_MODEL", "us.amazon.nova-micro-v1:0"))
    titan_embed_model: str = field(default_factory=lambda: getenv("TITAN_EMBED_MODEL", "amazon.titan-embed-text-v2:0"))
    embed_dimensions: int = 1024
    
    # Cache (optional - empty = in-memory fallback)
    cache_ttl: int = 43200  # 12 hours
    redis_url: str = field(default_factory=lambda: getenv("REDIS_URL", ""))  # Empty = memory fallback
    
    # Vector search (optional - empty = keyword fallback)  
    opensearch_host: str = field(default_factory=lambda: getenv("OPENSEARCH_HOST", ""))  # Empty = keyword fallback
    opensearch_index: str = field(default_factory=lambda: getenv("OPENSEARCH_INDEX", "icda-vectors"))


cfg = Config()
