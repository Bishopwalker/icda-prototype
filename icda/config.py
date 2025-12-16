"""Configuration with sensible defaults for LITE MODE (no external services)."""

from dataclasses import dataclass, field
from os import getenv


def _parse_bool(value: str, default: bool = True) -> bool:
    """Parse boolean from environment variable."""
    if not value:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def _parse_float(value: str, default: float) -> float:
    """Parse float from environment variable."""
    try:
        return float(value) if value else default
    except ValueError:
        return default


def _parse_int(value: str, default: int) -> int:
    """Parse int from environment variable."""
    try:
        return int(value) if value else default
    except ValueError:
        return default


@dataclass(slots=True, frozen=True)
class Config:
    # ==================== AWS (optional - empty = LITE MODE) ====================
    aws_region: str = field(default_factory=lambda: getenv("AWS_REGION", "us-east-1"))
    nova_model: str = field(default_factory=lambda: getenv("NOVA_MODEL", "us.amazon.nova-micro-v1:0"))
    titan_embed_model: str = field(default_factory=lambda: getenv("TITAN_EMBED_MODEL", "amazon.titan-embed-text-v2:0"))
    embed_dimensions: int = 1024

    # ==================== Cache (optional - empty = in-memory fallback) ====================
    cache_ttl: int = 43200  # 12 hours
    redis_url: str = field(default_factory=lambda: getenv("REDIS_URL", ""))

    # ==================== OpenSearch (optional - empty = keyword fallback) ====================
    opensearch_host: str = field(default_factory=lambda: getenv("OPENSEARCH_HOST", ""))
    opensearch_index: str = field(default_factory=lambda: getenv("OPENSEARCH_INDEX", "icda-vectors"))

    # ==================== Index Hierarchy (NEW) ====================
    index_master: str = field(default_factory=lambda: getenv("INDEX_MASTER", "icda-master"))
    index_code: str = field(default_factory=lambda: getenv("INDEX_CODE", "icda-code"))
    index_knowledge: str = field(default_factory=lambda: getenv("INDEX_KNOWLEDGE", "icda-knowledge"))
    index_customers: str = field(default_factory=lambda: getenv("INDEX_CUSTOMERS", "icda-customers"))

    # ==================== Gemini Enforcer (NEW) ====================
    gemini_api_key: str = field(default_factory=lambda: getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: getenv("GEMINI_MODEL", "gemini-2.0-flash"))
    gemini_chunk_threshold: float = field(
        default_factory=lambda: _parse_float(getenv("GEMINI_CHUNK_THRESHOLD", ""), 0.6)
    )
    gemini_query_sample_rate: float = field(
        default_factory=lambda: _parse_float(getenv("GEMINI_QUERY_SAMPLE_RATE", ""), 0.1)
    )
    gemini_validation_interval: int = field(
        default_factory=lambda: _parse_int(getenv("GEMINI_VALIDATION_INTERVAL", ""), 6)
    )

    # ==================== Feature Flags (NEW) ====================
    enable_federation: bool = field(
        default_factory=lambda: _parse_bool(getenv("ENABLE_FEDERATION", ""), True)
    )
    enable_gemini_enforcer: bool = field(
        default_factory=lambda: _parse_bool(getenv("ENABLE_GEMINI_ENFORCER", ""), True)
    )
    enable_code_index: bool = field(
        default_factory=lambda: _parse_bool(getenv("ENABLE_CODE_INDEX", ""), False)
    )
    admin_enabled: bool = field(
        default_factory=lambda: _parse_bool(getenv("ADMIN_ENABLED", ""), True)
    )

    def get_index_config(self) -> dict[str, str]:
        """Get index name configuration for IndexFederation."""
        return {
            "master": self.index_master,
            "code": self.index_code,
            "knowledge": self.index_knowledge,
            "customers": self.index_customers,
        }

    def is_gemini_available(self) -> bool:
        """Check if Gemini enforcer can be enabled."""
        return bool(self.gemini_api_key) and self.enable_gemini_enforcer

    def is_opensearch_available(self) -> bool:
        """Check if OpenSearch is configured."""
        return bool(self.opensearch_host)


cfg = Config()
