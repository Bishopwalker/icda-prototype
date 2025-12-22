"""
Secondary LLM Provider Package.

Provides provider-agnostic LLM client for quality enforcement.
Supports Gemini, OpenAI, Claude, and other providers.

Usage:
    from icda.llm import create_llm_client, LLMEnforcer

    client = create_llm_client()  # Auto-detects from env vars
    enforcer = LLMEnforcer(client=client)
"""

from .base import BaseLLMClient, LLMConfig, LLMResponse
from .factory import create_llm_client, get_available_providers
from .enforcer import LLMEnforcer
from .models import (
    ChunkQualityScore,
    ChunkGateResult,
    IndexHealthReport,
    QueryReviewResult,
    EnforcerMetrics,
)

__all__ = [
    # Base
    "BaseLLMClient",
    "LLMConfig",
    "LLMResponse",
    # Factory
    "create_llm_client",
    "get_available_providers",
    # Main enforcer
    "LLMEnforcer",
    # Models
    "ChunkQualityScore",
    "ChunkGateResult",
    "IndexHealthReport",
    "QueryReviewResult",
    "EnforcerMetrics",
]
