"""5-Agent Enforcer System for Knowledge Indexing.

This module implements the ultrathink enforcer pattern with 5 specialized agents:
1. IntakeGuardAgent - Validates input format, detects PR/batch content
2. SemanticMinerAgent - Extracts entities, patterns, relationships
3. ContextLinkerAgent - Links to existing knowledge, resolves references
4. QualityEnforcerAgent - Russian Olympic Judge validation
5. IndexSyncAgent - Indexes to OpenSearch, optimizes retrieval
"""

from .models import (
    EnforcerResult,
    BatchKnowledgeItem,
    BatchKnowledgeResult,
    BatchSummary,
    ContentType,
    ExtractionResult,
    AddressRule,
    AddressPattern,
    KnowledgeChunk,
    CrossReference,
)
from .quality_gates import (
    EnforcerGate,
    EnforcerGateResult,
    GateCategory,
)
from .orchestrator import EnforcerOrchestrator

__all__ = [
    "EnforcerOrchestrator",
    "EnforcerResult",
    "BatchKnowledgeItem",
    "BatchKnowledgeResult",
    "BatchSummary",
    "ContentType",
    "ExtractionResult",
    "AddressRule",
    "AddressPattern",
    "KnowledgeChunk",
    "CrossReference",
    "EnforcerGate",
    "EnforcerGateResult",
    "GateCategory",
]
