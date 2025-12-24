"""Query Agent Pipeline Models.

Data structures for the 8-agent query handling system.
Follows the same patterns as address_models.py for consistency.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# Re-export existing enums from classifier for consistency
from icda.classifier import QueryComplexity, QueryIntent


class QueryDomain(str, Enum):
    """Domain areas that a query can target."""
    CUSTOMER = "customer"       # Customer data queries
    ADDRESS = "address"         # Address verification
    KNOWLEDGE = "knowledge"     # Knowledge base queries
    STATS = "stats"             # Statistical/aggregate queries
    GENERAL = "general"         # General questions


class ResponseStatus(str, Enum):
    """Status of the final response after enforcement."""
    APPROVED = "approved"       # Passed all quality gates
    MODIFIED = "modified"       # Passed after modifications (redaction, etc.)
    REJECTED = "rejected"       # Failed quality gates
    FALLBACK = "fallback"       # Used fallback response


class QualityGate(str, Enum):
    """Quality gates for response enforcement."""
    RESPONSIVE = "responsive"           # Response addresses the query
    FACTUAL = "factual"                 # Data matches DB results
    PII_SAFE = "pii_safe"               # No leaked sensitive data
    COMPLETE = "complete"               # All requested info included
    COHERENT = "coherent"               # Response is well-formed
    ON_TOPIC = "on_topic"               # No off-topic content
    CONFIDENCE_MET = "confidence_met"   # Above threshold


class SearchStrategy(str, Enum):
    """Search strategies available."""
    EXACT = "exact"             # Direct lookup
    FUZZY = "fuzzy"             # Typo-tolerant
    SEMANTIC = "semantic"       # Vector-based
    HYBRID = "hybrid"           # Combined text + semantic
    KEYWORD = "keyword"         # Simple keyword matching


class MatchQuality(str, Enum):
    """Quality level of search result matches.

    Used to indicate how confident we are in the search results.
    Displayed to users so they know if results are exact or approximate.
    """
    EXACT = "exact"             # Direct lookup or 100% filter match
    PARTIAL = "partial"         # Good match, confidence > 0.7
    FUZZY = "fuzzy"             # Typo-tolerant, confidence 0.5-0.7
    SEMANTIC = "semantic"       # Vector similarity match
    APPROXIMATE = "approximate" # Low confidence, < 0.5


class ModelTier(str, Enum):
    """Nova model tiers for routing."""
    MICRO = "nova-micro"
    LITE = "nova-lite"
    PRO = "nova-pro"
    FALLBACK = "fallback"


class SuggestionType(str, Enum):
    """Types of suggestions the SuggestionAgent can generate."""
    TYPO_FIX = "typo_fix"               # "Did you mean 'California'?"
    QUERY_REFINEMENT = "refinement"      # "Try adding a state filter"
    FOLLOW_UP = "follow_up"              # "Show their addresses"
    DISAMBIGUATION = "disambiguate"      # "Multiple customers named John"
    FILTER_SUGGESTION = "filter_add"     # "Add 'high movers' filter"
    RESULT_EXPANSION = "expansion"       # "Try neighboring states?"


class PersonalityStyle(str, Enum):
    """Personality styles for response generation."""
    WITTY_EXPERT = "witty_expert"        # Clever and knowledgeable
    FRIENDLY_PROFESSIONAL = "friendly"   # Warm but businesslike
    CASUAL_FUN = "casual"                # Playful with emojis
    MINIMAL = "minimal"                  # Subtle warmth only


# ============================================================================
# Memory and Personality Dataclasses
# ============================================================================

@dataclass(slots=True)
class MemoryEntity:
    """A remembered entity from conversation.

    Attributes:
        entity_id: Unique identifier (CRID, name, etc.).
        entity_type: Type of entity (customer, location, preference).
        canonical_name: Primary reference name.
        aliases: Alternative references ("that customer", "him").
        attributes: Stored attributes (state, moves, etc.).
        first_mentioned: Timestamp when first mentioned.
        last_accessed: Timestamp of last access (for LRU).
        mention_count: How many times referenced.
        confidence: How sure we are this is the entity.
    """
    entity_id: str
    entity_type: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    first_mentioned: float = 0.0
    last_accessed: float = 0.0
    mention_count: int = 1
    confidence: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "canonical_name": self.canonical_name,
            "aliases": self.aliases,
            "attributes": self.attributes,
            "first_mentioned": self.first_mentioned,
            "last_accessed": self.last_accessed,
            "mention_count": self.mention_count,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntity":
        """Create from dictionary."""
        return cls(
            entity_id=data["entity_id"],
            entity_type=data["entity_type"],
            canonical_name=data["canonical_name"],
            aliases=data.get("aliases", []),
            attributes=data.get("attributes", {}),
            first_mentioned=data.get("first_mentioned", 0.0),
            last_accessed=data.get("last_accessed", 0.0),
            mention_count=data.get("mention_count", 1),
            confidence=data.get("confidence", 0.8),
        )


@dataclass(slots=True)
class MemoryContext:
    """Result from MemoryAgent retrieval.

    Attributes:
        recalled_entities: Entities recalled from memory.
        active_customer: The customer currently being discussed.
        active_location: Current geographic focus (state, city).
        user_preferences: Learned user preferences.
        resolved_pronouns: Pronoun to entity mappings.
        recall_confidence: Confidence in memory recall.
        memory_signals: Debug info about recall process.
    """
    recalled_entities: list[MemoryEntity] = field(default_factory=list)
    active_customer: MemoryEntity | None = None
    active_location: dict[str, str] | None = None
    user_preferences: dict[str, Any] = field(default_factory=dict)
    resolved_pronouns: dict[str, str] = field(default_factory=dict)
    recall_confidence: float = 0.0
    memory_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "recalled_entities": [e.to_dict() for e in self.recalled_entities],
            "active_customer": self.active_customer.to_dict() if self.active_customer else None,
            "active_location": self.active_location,
            "user_preferences": self.user_preferences,
            "resolved_pronouns": self.resolved_pronouns,
            "recall_confidence": self.recall_confidence,
            "memory_signals": self.memory_signals,
        }


@dataclass(slots=True)
class Suggestion:
    """A single suggestion for query improvement.

    Attributes:
        suggestion_type: Type of suggestion.
        original: What triggered the suggestion.
        suggested: The suggested correction/action.
        reason: Why this is suggested.
        confidence: Confidence in the suggestion.
        action_query: Ready-to-execute query if applicable.
    """
    suggestion_type: SuggestionType
    original: str
    suggested: str
    reason: str
    confidence: float = 0.7
    action_query: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "type": self.suggestion_type.value,
            "original": self.original,
            "suggested": self.suggested,
            "reason": self.reason,
            "confidence": self.confidence,
        }
        if self.action_query:
            result["action_query"] = self.action_query
        return result


@dataclass(slots=True)
class SuggestionContext:
    """Result from SuggestionAgent.

    Attributes:
        suggestions: List of suggestions (max 3).
        primary_suggestion: The most important suggestion.
        follow_up_prompts: Quick follow-up options.
        suggestion_confidence: Overall confidence.
    """
    suggestions: list[Suggestion] = field(default_factory=list)
    primary_suggestion: Suggestion | None = None
    follow_up_prompts: list[str] = field(default_factory=list)
    suggestion_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "suggestions": [s.to_dict() for s in self.suggestions],
            "primary_suggestion": self.primary_suggestion.to_dict() if self.primary_suggestion else None,
            "follow_up_prompts": self.follow_up_prompts,
            "suggestion_confidence": self.suggestion_confidence,
        }


@dataclass(slots=True)
class PersonalityConfig:
    """Configuration for personality agent.

    Attributes:
        style: Personality style to use.
        warmth_level: How warm to be (0=clinical, 1=very warm).
        humor_enabled: Whether to add appropriate humor.
        empathy_enabled: Whether to show empathy on failures.
    """
    style: PersonalityStyle = PersonalityStyle.WITTY_EXPERT
    warmth_level: float = 0.7
    humor_enabled: bool = True
    empathy_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "style": self.style.value,
            "warmth_level": self.warmth_level,
            "humor_enabled": self.humor_enabled,
            "empathy_enabled": self.empathy_enabled,
        }


@dataclass(slots=True)
class PersonalityContext:
    """Result from PersonalityAgent enhancement.

    Attributes:
        enhanced_response: Response with personality applied.
        original_response: Original unmodified response.
        personality_applied: Whether personality was applied.
        enhancements_made: List of enhancements made.
        tone_score: Warmth level of final response.
    """
    enhanced_response: str
    original_response: str
    personality_applied: bool = True
    enhancements_made: list[str] = field(default_factory=list)
    tone_score: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "enhanced_response": self.enhanced_response,
            "original_response": self.original_response,
            "personality_applied": self.personality_applied,
            "enhancements_made": self.enhancements_made,
            "tone_score": self.tone_score,
        }


# ============================================================================
# Failure Tracking and Escalation Dataclasses
# ============================================================================

@dataclass(slots=True)
class FailureRecord:
    """Record of a failed query attempt for tracking and escalation.

    Used by FailureTracker to remember which queries failed and why,
    enabling the system to try different strategies on retry.

    Attributes:
        query_hash: Hash of normalized query for matching repeat queries.
        original_query: Original query text.
        failed_gates: Which quality gates failed.
        failed_strategies: Strategies that were tried and failed.
        last_response: The response that was rejected.
        failure_count: Number of times this query pattern failed.
        created_at: Timestamp of first failure.
        last_attempt: Timestamp of most recent attempt.
        session_id: Session this failure belongs to.
    """
    query_hash: str
    original_query: str
    failed_gates: list[QualityGate] = field(default_factory=list)
    failed_strategies: list[str] = field(default_factory=list)
    last_response: str = ""
    failure_count: int = 1
    created_at: float = 0.0
    last_attempt: float = 0.0
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "query_hash": self.query_hash,
            "original_query": self.original_query,
            "failed_gates": [g.value for g in self.failed_gates],
            "failed_strategies": self.failed_strategies,
            "last_response": self.last_response[:200] if self.last_response else "",
            "failure_count": self.failure_count,
            "created_at": self.created_at,
            "last_attempt": self.last_attempt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FailureRecord":
        """Create from dictionary."""
        return cls(
            query_hash=data["query_hash"],
            original_query=data["original_query"],
            failed_gates=[QualityGate(g) for g in data.get("failed_gates", [])],
            failed_strategies=data.get("failed_strategies", []),
            last_response=data.get("last_response", ""),
            failure_count=data.get("failure_count", 1),
            created_at=data.get("created_at", 0.0),
            last_attempt=data.get("last_attempt", 0.0),
            session_id=data.get("session_id"),
        )


@dataclass(slots=True)
class EscalationContext:
    """Context for strategy escalation after failed queries.

    Provides information about previous failures and which strategies
    to try or skip when processing a retry query.

    Attributes:
        is_retry: Whether this is a retry of a previously failed query.
        previous_failures: History of failures for this query pattern.
        excluded_strategies: Strategies to skip (previously failed).
        escalation_level: Current escalation level (0-4).
        user_message: Message to show user about escalation.
        recommended_strategies: Strategies to try in order.
    """
    is_retry: bool = False
    previous_failures: list[FailureRecord] = field(default_factory=list)
    excluded_strategies: list[str] = field(default_factory=list)
    escalation_level: int = 0
    user_message: str | None = None
    recommended_strategies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "is_retry": self.is_retry,
            "excluded_strategies": self.excluded_strategies,
            "escalation_level": self.escalation_level,
            "user_message": self.user_message,
            "recommended_strategies": self.recommended_strategies,
        }


@dataclass(slots=True)
class CityStateMismatch:
    """Result of city/state validation.

    Detects when a city doesn't match the expected state,
    e.g., "Miami, TX" when Miami is typically in Florida.

    Attributes:
        has_mismatch: Whether a mismatch was detected.
        city: The city that was queried.
        stated_state: The state provided in the query.
        expected_state: The expected/typical state for this city.
        suggestion: Human-readable suggestion message.
        confidence: Confidence in the mismatch detection.
        is_ambiguous: True if city exists in multiple states.
    """
    has_mismatch: bool
    city: str
    stated_state: str
    expected_state: str | None = None
    suggestion: str | None = None
    confidence: float = 0.0
    is_ambiguous: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "has_mismatch": self.has_mismatch,
            "city": self.city,
            "stated_state": self.stated_state,
            "expected_state": self.expected_state,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
            "is_ambiguous": self.is_ambiguous,
        }


# ============================================================================
# Token and Pagination Dataclasses
# ============================================================================

@dataclass(slots=True)
class TokenUsage:
    """Token usage statistics from a model call.

    Attributes:
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens generated.
        total_tokens: Total tokens used.
        context_limit: Maximum context window size.
    """
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    context_limit: int = 300000  # Nova Lite context window

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """Allow aggregation of token usage across multiple calls."""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            context_limit=self.context_limit,
        )

    @property
    def percentage_used(self) -> float:
        """Calculate percentage of context window used."""
        if self.context_limit <= 0:
            return 0.0
        return (self.total_tokens / self.context_limit) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "context_limit": self.context_limit,
            "percentage_used": round(self.percentage_used, 2),
        }


@dataclass(slots=True)
class PaginationInfo:
    """Pagination metadata for large result sets.

    Attributes:
        total_count: Total number of matching records.
        returned_count: Number of records returned in response.
        has_more: Whether there are more results available.
        suggest_download: True if results exceed display limit.
        download_token: Token for fetching full results via download endpoint.
        download_expires_at: ISO timestamp when token expires.
        preview_size: Number of results shown as preview.
    """
    total_count: int
    returned_count: int
    has_more: bool
    suggest_download: bool
    download_token: str | None = None
    download_expires_at: str | None = None
    preview_size: int = 15

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "total_count": self.total_count,
            "returned_count": self.returned_count,
            "has_more": self.has_more,
            "suggest_download": self.suggest_download,
            "preview_size": self.preview_size,
        }
        if self.download_token:
            result["download_token"] = self.download_token
        if self.download_expires_at:
            result["download_expires_at"] = self.download_expires_at
        return result


@dataclass(slots=True)
class ModelRoutingDecision:
    """Result of model routing decision.

    Attributes:
        model_id: Full model ID for Bedrock.
        model_tier: Model tier (micro/lite/pro).
        reason: Explanation for the routing decision.
        confidence_factor: Confidence that influenced decision.
    """
    model_id: str
    model_tier: ModelTier
    reason: str
    confidence_factor: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "model_id": self.model_id,
            "model_tier": self.model_tier.value,
            "reason": self.reason,
            "confidence_factor": self.confidence_factor,
        }


# ============================================================================
# Agent Result Dataclasses
# ============================================================================

@dataclass(slots=True)
class IntentResult:
    """Result from IntentAgent classification.

    Attributes:
        primary_intent: Main detected query intent.
        secondary_intents: Additional intents detected.
        confidence: Classification confidence (0.0 - 1.0).
        domains: Relevant query domains.
        complexity: Query complexity level.
        suggested_tools: Tools that might be useful.
        raw_signals: Debug info about classification signals.
    """
    primary_intent: QueryIntent
    secondary_intents: list[QueryIntent] = field(default_factory=list)
    confidence: float = 0.5
    domains: list[QueryDomain] = field(default_factory=list)
    complexity: QueryComplexity = QueryComplexity.MEDIUM
    suggested_tools: list[str] = field(default_factory=list)
    raw_signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "primary_intent": self.primary_intent.value,
            "secondary_intents": [i.value for i in self.secondary_intents],
            "confidence": self.confidence,
            "domains": [d.value for d in self.domains],
            "complexity": self.complexity.value,
            "suggested_tools": self.suggested_tools,
        }


@dataclass(slots=True)
class QueryContext:
    """Result from ContextAgent extraction.

    Attributes:
        session_history: Previous conversation messages.
        referenced_entities: CRIDs, names mentioned before.
        geographic_context: State, city, zip from prior conversation.
        user_preferences: Inferred preferences from history.
        prior_results: Last query results for follow-ups.
        is_follow_up: Whether this is a follow-up question.
        context_confidence: Confidence in extracted context.
        memory_entities: Entity IDs from memory recall.
        resolved_pronouns: Pronoun to entity mappings from memory.
        memory_confidence: Confidence from memory recall.
    """
    session_history: list[dict[str, Any]] = field(default_factory=list)
    referenced_entities: list[str] = field(default_factory=list)
    geographic_context: dict[str, str | None] = field(default_factory=dict)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    prior_results: list[dict[str, Any]] | None = None
    is_follow_up: bool = False
    context_confidence: float = 0.0
    # Memory integration fields
    memory_entities: list[str] = field(default_factory=list)
    resolved_pronouns: dict[str, str] = field(default_factory=dict)
    memory_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "history_length": len(self.session_history),
            "referenced_entities": self.referenced_entities,
            "geographic_context": self.geographic_context,
            "is_follow_up": self.is_follow_up,
            "context_confidence": self.context_confidence,
            "memory_entities": self.memory_entities,
            "resolved_pronouns": self.resolved_pronouns,
            "memory_confidence": self.memory_confidence,
        }


@dataclass(slots=True)
class ParsedQuery:
    """Result from ParserAgent normalization.

    Attributes:
        original_query: Original user query.
        normalized_query: Cleaned/normalized query.
        entities: Extracted entities by type.
        filters: Extracted filter criteria.
        date_range: Date range if specified.
        sort_preference: Requested sorting.
        limit: Result limit requested.
        is_follow_up: Whether this continues previous query.
        resolution_notes: Notes about normalizations made.
    """
    original_query: str
    normalized_query: str
    entities: dict[str, list[str]] = field(default_factory=dict)
    filters: dict[str, Any] = field(default_factory=dict)
    date_range: tuple[str, str] | None = None
    sort_preference: str | None = None
    limit: int = 10
    is_follow_up: bool = False
    resolution_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "original_query": self.original_query,
            "normalized_query": self.normalized_query,
            "entities": self.entities,
            "filters": self.filters,
            "date_range": self.date_range,
            "sort_preference": self.sort_preference,
            "limit": self.limit,
            "is_follow_up": self.is_follow_up,
            "resolution_notes": self.resolution_notes,
        }


@dataclass(slots=True)
class ResolvedQuery:
    """Result from ResolverAgent entity resolution.

    Attributes:
        resolved_crids: Validated customer CRIDs.
        resolved_customers: Direct lookup results if applicable.
        expanded_scope: Multi-state or broader scope info.
        fallback_strategies: Strategies to try if primary fails.
        resolution_confidence: Confidence in resolution.
        unresolved_entities: Entities that couldn't be resolved.
    """
    resolved_crids: list[str] = field(default_factory=list)
    resolved_customers: list[dict[str, Any]] | None = None
    expanded_scope: dict[str, Any] = field(default_factory=dict)
    fallback_strategies: list[str] = field(default_factory=list)
    resolution_confidence: float = 0.0
    unresolved_entities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "resolved_crids": self.resolved_crids,
            "customers_found": len(self.resolved_customers) if self.resolved_customers else 0,
            "expanded_scope": self.expanded_scope,
            "fallback_strategies": self.fallback_strategies,
            "resolution_confidence": self.resolution_confidence,
            "unresolved_entities": self.unresolved_entities,
        }


@dataclass(slots=True)
class SearchResult:
    """Result from SearchAgent execution.

    Attributes:
        strategy_used: Which search strategy was used.
        results: Search results.
        total_matches: Total number of matches.
        search_metadata: Timing, scores, etc.
        alternatives_tried: Strategies attempted before success.
        search_confidence: Confidence in results.
        match_quality: Quality level of the matches (EXACT/PARTIAL/FUZZY/etc).
        state_not_available: True if requested state not in dataset.
        requested_state: State code that was requested but not available.
        requested_state_name: Full name of requested state.
        available_states: List of states that are available.
        available_states_with_counts: Dict of state -> customer count.
        suggestion: Helpful suggestion message.
    """
    strategy_used: SearchStrategy
    results: list[dict[str, Any]] = field(default_factory=list)
    total_matches: int = 0
    search_metadata: dict[str, Any] = field(default_factory=dict)
    alternatives_tried: list[str] = field(default_factory=list)
    search_confidence: float = 0.0
    # Match quality field - indicates how confident we are in the results
    match_quality: MatchQuality = MatchQuality.PARTIAL
    # State availability fields
    state_not_available: bool = False
    requested_state: str | None = None
    requested_state_name: str | None = None
    available_states: list[str] = field(default_factory=list)
    available_states_with_counts: dict[str, int] = field(default_factory=dict)
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "strategy_used": self.strategy_used.value,
            "results_count": len(self.results),
            "total_matches": self.total_matches,
            "alternatives_tried": self.alternatives_tried,
            "search_confidence": self.search_confidence,
            "match_quality": self.match_quality.value,
        }
        # Add state availability info if state not available
        if self.state_not_available:
            result["state_not_available"] = True
            result["requested_state"] = self.requested_state
            result["requested_state_name"] = self.requested_state_name
            result["available_states"] = self.available_states
            result["available_states_with_counts"] = self.available_states_with_counts
            result["suggestion"] = self.suggestion
        return result


@dataclass(slots=True)
class KnowledgeContext:
    """Result from KnowledgeAgent RAG retrieval.

    Attributes:
        relevant_chunks: Retrieved knowledge chunks.
        total_chunks_found: Total chunks matching query.
        categories_searched: Knowledge categories searched.
        tags_matched: Tags that matched.
        rag_confidence: Confidence in RAG results.
    """
    relevant_chunks: list[dict[str, Any]] = field(default_factory=list)
    total_chunks_found: int = 0
    categories_searched: list[str] = field(default_factory=list)
    tags_matched: list[str] = field(default_factory=list)
    rag_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "chunks_count": len(self.relevant_chunks),
            "total_chunks_found": self.total_chunks_found,
            "categories_searched": self.categories_searched,
            "tags_matched": self.tags_matched,
            "rag_confidence": self.rag_confidence,
        }


@dataclass(slots=True)
class NovaResponse:
    """Result from NovaAgent AI generation.

    Attributes:
        response_text: Generated response text.
        tools_used: Tools that were called.
        tool_results: Results from tool calls.
        model_used: Which Nova model was used.
        token_usage: Token usage statistics.
        ai_confidence: Confidence in response.
        raw_response: Raw API response for debugging.
        routing_decision: Model routing decision info.
    """
    response_text: str
    tools_used: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    model_used: str = "nova-micro"
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    ai_confidence: float = 0.0
    raw_response: dict[str, Any] | None = None
    routing_decision: ModelRoutingDecision | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "response_text": self.response_text,
            "tools_used": self.tools_used,
            "model_used": self.model_used,
            "token_usage": self.token_usage.to_dict(),
            "ai_confidence": self.ai_confidence,
        }
        if self.routing_decision:
            result["routing_decision"] = self.routing_decision.to_dict()
        return result


@dataclass(slots=True)
class QualityGateResult:
    """Result of a single quality gate check."""
    gate: QualityGate
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "gate": self.gate.value,
            "passed": self.passed,
            "message": self.message,
        }


@dataclass(slots=True)
class EnforcedResponse:
    """Result from EnforcerAgent validation.

    Attributes:
        final_response: Final response after enforcement.
        original_response: Original response before modifications.
        quality_score: Overall quality score (0.0 - 1.0).
        gates_passed: Quality gates that passed.
        gates_failed: Quality gates that failed.
        modifications: Changes made during enforcement.
        status: Final response status.
    """
    final_response: str
    original_response: str
    quality_score: float = 0.0
    gates_passed: list[QualityGateResult] = field(default_factory=list)
    gates_failed: list[QualityGateResult] = field(default_factory=list)
    modifications: list[str] = field(default_factory=list)
    status: ResponseStatus = ResponseStatus.APPROVED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "final_response": self.final_response,
            "quality_score": self.quality_score,
            "gates_passed": [g.to_dict() for g in self.gates_passed],
            "gates_failed": [g.to_dict() for g in self.gates_failed],
            "modifications": self.modifications,
            "status": self.status.value,
        }


# ============================================================================
# Pipeline Dataclasses
# ============================================================================

@dataclass(slots=True)
class PipelineStage:
    """Record of a single pipeline stage execution.

    Attributes:
        agent: Agent name (intent, context, parser, etc.).
        output: Output data from the agent.
        time_ms: Execution time in milliseconds.
        success: Whether the stage completed successfully.
        error: Error message if failed.
        confidence: Confidence score from the agent.
        token_usage: Token usage for this stage (if applicable).
        route_decision: Routing decision made in this stage.
        debug_info: Additional debug information.
    """
    agent: str
    output: dict[str, Any]
    time_ms: int
    success: bool = True
    error: str | None = None
    confidence: float | None = None
    token_usage: TokenUsage | None = None
    route_decision: dict[str, Any] | None = None
    debug_info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "agent": self.agent,
            "output": self.output,
            "time_ms": self.time_ms,
            "success": self.success,
            "error": self.error,
        }
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.token_usage:
            result["token_usage"] = self.token_usage.to_dict()
        if self.route_decision:
            result["route_decision"] = self.route_decision
        if self.debug_info:
            result["debug_info"] = self.debug_info
        return result


@dataclass(slots=True)
class PipelineTrace:
    """Complete trace of pipeline execution.

    Attributes:
        stages: List of pipeline stages executed.
        total_time_ms: Total execution time.
        success: Whether pipeline completed successfully.
        total_token_usage: Aggregated token usage across all stages.
        model_routing_decision: Final model routing decision.
        min_confidence: Minimum confidence across all stages.
    """
    stages: list[PipelineStage] = field(default_factory=list)
    total_time_ms: int = 0
    success: bool = True
    total_token_usage: TokenUsage = field(default_factory=TokenUsage)
    model_routing_decision: ModelRoutingDecision | None = None
    min_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "stages": [s.to_dict() for s in self.stages],
            "total_time_ms": self.total_time_ms,
            "success": self.success,
            "total_token_usage": self.total_token_usage.to_dict(),
        }
        if self.model_routing_decision:
            result["model_routing_decision"] = self.model_routing_decision.to_dict()
        if self.min_confidence is not None:
            result["min_confidence"] = self.min_confidence
        return result

    def add_stage(
        self,
        agent: str,
        output: dict[str, Any],
        time_ms: int,
        success: bool = True,
        error: str | None = None,
        confidence: float | None = None,
        token_usage: TokenUsage | None = None,
    ) -> PipelineStage:
        """Add a new stage to the trace."""
        stage = PipelineStage(
            agent=agent,
            output=output,
            time_ms=time_ms,
            success=success,
            error=error,
            confidence=confidence,
            token_usage=token_usage,
        )
        self.stages.append(stage)

        # Update aggregates
        if confidence is not None:
            if self.min_confidence is None or confidence < self.min_confidence:
                self.min_confidence = confidence

        if token_usage:
            self.total_token_usage = self.total_token_usage + token_usage

        return stage


@dataclass(slots=True)
class QueryResult:
    """Final result of the query pipeline.

    Attributes:
        success: Whether the query was successful.
        response: Final response text.
        route: Which route was taken (cache, database, nova).
        tools_used: Tools that were called.
        quality_score: Overall quality score.
        latency_ms: Total latency.
        trace: Pipeline execution trace.
        metadata: Additional metadata.
        token_usage: Total token usage for the query.
        pagination: Pagination info for large result sets.
        model_used: Which Nova model was used.
        guardrails_active: Whether guardrails were active.
        guardrails_bypassed: Whether guardrails were bypassed.
        results: Raw search results for pagination display.
    """
    success: bool
    response: str
    route: str = "nova"
    tools_used: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    latency_ms: int = 0
    trace: PipelineTrace | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    pagination: PaginationInfo | None = None
    model_used: str = "nova-micro"
    guardrails_active: bool = True
    guardrails_bypassed: bool = False
    results: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "success": self.success,
            "response": self.response,
            "route": self.route,
            "tools_used": self.tools_used,
            "quality_score": self.quality_score,
            "latency_ms": self.latency_ms,
            "trace": self.trace.to_dict() if self.trace else None,
            "token_usage": self.token_usage.to_dict(),
            "model_used": self.model_used,
            "guardrails_active": self.guardrails_active,
            "guardrails_bypassed": self.guardrails_bypassed,
        }
        if self.pagination:
            result["pagination"] = self.pagination.to_dict()
        if self.results:
            result["results"] = self.results
        return result
