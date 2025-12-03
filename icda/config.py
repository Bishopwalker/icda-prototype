from dataclasses import dataclass, field
from os import getenv

@dataclass(slots=True, frozen=True)
class Config:
    aws_region: str = field(default_factory=lambda: getenv("AWS_REGION", "us-east-1"))
    nova_model: str = field(default_factory=lambda: getenv("NOVA_MODEL", "us.amazon.nova-micro-v1:0"))
    titan_embed_model: str = field(default_factory=lambda: getenv("TITAN_EMBED_MODEL", "amazon.titan-embed-text-v2:0"))
    embed_dimensions: int = 1024
    cache_ttl: int = 43200  # 12 hours
    redis_url: str = field(default_factory=lambda: getenv("REDIS_URL", "redis://localhost:6379"))
    opensearch_host: str = field(default_factory=lambda: getenv("OPENSEARCH_HOST", ""))
    opensearch_index: str = field(default_factory=lambda: getenv("OPENSEARCH_INDEX", "icda-vectors"))

cfg = Config()
