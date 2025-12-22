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
    # Default to Nova Lite - Micro has stricter content filters that block customer data
    nova_model: str = field(default_factory=lambda: getenv("NOVA_MODEL", "us.amazon.nova-lite-v1:0"))
    titan_embed_model: str = field(default_factory=lambda: getenv("TITAN_EMBED_MODEL", "amazon.titan-embed-text-v2:0"))
    embed_dimensions: int = 1024

    # ==================== Nova Model Routing (NEW) ====================
    # Nova Lite - default for all queries (Micro has content filter issues)
    nova_lite_model: str = field(default_factory=lambda: getenv("NOVA_LITE_MODEL", "us.amazon.nova-lite-v1:0"))
    # Nova Pro - for complex queries, low confidence, multi-part queries
    nova_pro_model: str = field(default_factory=lambda: getenv("NOVA_PRO_MODEL", "us.amazon.nova-pro-v1:0"))
    # Confidence threshold - below this triggers escalation to Pro
    model_routing_threshold: float = field(
        default_factory=lambda: _parse_float(getenv("MODEL_ROUTING_THRESHOLD", ""), 0.6)
    )
    # Pagination threshold - above this suggests download
    pagination_threshold: int = field(
        default_factory=lambda: _parse_int(getenv("PAGINATION_THRESHOLD", ""), 50)
    )
    # Preview size for paginated results
    pagination_preview_size: int = field(
        default_factory=lambda: _parse_int(getenv("PAGINATION_PREVIEW_SIZE", ""), 15)
    )

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

    # ==================== Secondary LLM Enforcer ====================
    # Provider: auto, gemini, openai, claude, openrouter
    secondary_llm_provider: str = field(
        default_factory=lambda: getenv("SECONDARY_LLM_PROVIDER", "auto")
    )
    # Provider-specific API keys (auto-detection checks all)
    gemini_api_key: str = field(default_factory=lambda: getenv("GEMINI_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: getenv("ANTHROPIC_API_KEY", ""))
    openrouter_api_key: str = field(default_factory=lambda: getenv("OPENROUTER_API_KEY", ""))
    # Model override (empty = use provider default)
    secondary_llm_model: str = field(
        default_factory=lambda: getenv("SECONDARY_LLM_MODEL", "")
    )
    # Enforcement thresholds
    enforcer_chunk_threshold: float = field(
        default_factory=lambda: _parse_float(getenv("ENFORCER_CHUNK_THRESHOLD", ""), 0.6)
    )
    enforcer_query_sample_rate: float = field(
        default_factory=lambda: _parse_float(getenv("ENFORCER_QUERY_SAMPLE_RATE", ""), 0.1)
    )
    enforcer_validation_interval: int = field(
        default_factory=lambda: _parse_int(getenv("ENFORCER_VALIDATION_INTERVAL", ""), 6)
    )

    # ==================== Feature Flags ====================
    enable_federation: bool = field(
        default_factory=lambda: _parse_bool(getenv("ENABLE_FEDERATION", ""), True)
    )
    enable_llm_enforcer: bool = field(
        default_factory=lambda: _parse_bool(getenv("ENABLE_LLM_ENFORCER", ""), True)
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

    def is_enforcer_available(self) -> bool:
        """Check if LLM enforcer can be enabled (any provider)."""
        if not self.enable_llm_enforcer:
            return False
        # Check if any provider API key is available
        return bool(
            self.gemini_api_key or
            self.openai_api_key or
            self.anthropic_api_key or
            self.openrouter_api_key
        )

    # Backward compatibility
    def is_gemini_available(self) -> bool:
        """Deprecated: Use is_enforcer_available instead."""
        return self.is_enforcer_available()

    def is_opensearch_available(self) -> bool:
        """Check if OpenSearch is configured."""
        return bool(self.opensearch_host)


cfg = Config()
