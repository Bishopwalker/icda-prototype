"""Agent modules for ICDA.

Includes:
- Address verification orchestrator (5-agent pipeline)
- Query orchestrator (11-agent pipeline with memory, personality, suggestions)
- All individual agents
"""

# Address verification orchestrator
from .orchestrator import AddressAgentOrchestrator

# Query pipeline orchestrator
from .query_orchestrator import QueryOrchestrator, create_query_orchestrator

# Individual query agents
from .intent_agent import IntentAgent
from .context_agent import ContextAgent
from .parser_agent import ParserAgent
from .resolver_agent import ResolverAgent
from .search_agent import SearchAgent
from .knowledge_agent import KnowledgeAgent
from .nova_agent import NovaAgent
from .enforcer_agent import EnforcerAgent

# New agents for memory, personality, and suggestions
from .memory_agent import MemoryAgent
from .personality_agent import PersonalityAgent
from .suggestion_agent import SuggestionAgent

# Tool registry
from .tool_registry import ToolRegistry, ToolSpec, ToolCategory, create_default_registry

# Models
from .models import (
    QueryDomain,
    ResponseStatus,
    QualityGate,
    SearchStrategy,
    SuggestionType,
    PersonalityStyle,
    IntentResult,
    QueryContext,
    ParsedQuery,
    ResolvedQuery,
    SearchResult,
    KnowledgeContext,
    NovaResponse,
    QualityGateResult,
    EnforcedResponse,
    PipelineStage,
    PipelineTrace,
    QueryResult,
    # Memory and personality models
    MemoryEntity,
    MemoryContext,
    Suggestion,
    SuggestionContext,
    PersonalityConfig,
    PersonalityContext,
)

__all__ = [
    # Orchestrators
    "AddressAgentOrchestrator",
    "QueryOrchestrator",
    "create_query_orchestrator",
    # Core agents
    "IntentAgent",
    "ContextAgent",
    "ParserAgent",
    "ResolverAgent",
    "SearchAgent",
    "KnowledgeAgent",
    "NovaAgent",
    "EnforcerAgent",
    # New agents
    "MemoryAgent",
    "PersonalityAgent",
    "SuggestionAgent",
    # Tool registry
    "ToolRegistry",
    "ToolSpec",
    "ToolCategory",
    "create_default_registry",
    # Models
    "QueryDomain",
    "ResponseStatus",
    "QualityGate",
    "SearchStrategy",
    "SuggestionType",
    "PersonalityStyle",
    "IntentResult",
    "QueryContext",
    "ParsedQuery",
    "ResolvedQuery",
    "SearchResult",
    "KnowledgeContext",
    "NovaResponse",
    "QualityGateResult",
    "EnforcedResponse",
    "PipelineStage",
    "PipelineTrace",
    "QueryResult",
    "MemoryEntity",
    "MemoryContext",
    "Suggestion",
    "SuggestionContext",
    "PersonalityConfig",
    "PersonalityContext",
]
