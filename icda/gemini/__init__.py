"""
Gemini Enforcer Package.

Provides 3-level quality enforcement using Google Gemini:
- Level 1: Chunk Quality Gate (pre-index)
- Level 2: Index Validation (periodic)
- Level 3: Query Review (runtime)

Usage:
    from icda.gemini import GeminiEnforcer

    enforcer = GeminiEnforcer()
    result = await enforcer.evaluate_chunk(chunk_id, content)
"""

from .client import GeminiClient, GeminiConfig
from .enforcer import GeminiEnforcer
from .models import (
    ChunkQualityScore,
    ChunkGateResult,
    IndexHealthReport,
    QueryReviewResult,
    EnforcerMetrics,
)

__all__ = [
    # Client
    "GeminiClient",
    "GeminiConfig",
    # Main enforcer
    "GeminiEnforcer",
    # Models
    "ChunkQualityScore",
    "ChunkGateResult",
    "IndexHealthReport",
    "QueryReviewResult",
    "EnforcerMetrics",
]
