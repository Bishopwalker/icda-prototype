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


class ModelTier(str, Enum):
    """Nova model tiers for routing."""
    MICRO = "nova-micro"
    LITE = "nova-lite"
    PRO = "nova-pro"
    FALLBACK = "fallback"


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
        preview_size: Number of results shown as preview.
    """
    total_count: int
    returned_count: int
    has_more: bool
    suggest_download: bool
    download_token: str | None = None
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
    """
    session_history: list[dict[str, Any]] = field(default_factory=list)
    referenced_entities: list[str] = field(default_factory=list)
    geographic_context: dict[str, str | None] = field(default_factory=dict)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    prior_results: list[dict[str, Any]] | None = None
    is_follow_up: bool = False
    context_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "history_length": len(self.session_history),
            "referenced_entities": self.referenced_entities,
            "geographic_context": self.geographic_context,
            "is_follow_up": self.is_follow_up,
            "context_confidence": self.context_confidence,
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
    """
    strategy_used: SearchStrategy
    results: list[dict[str, Any]] = field(default_factory=list)
    total_matches: int = 0
    search_metadata: dict[str, Any] = field(default_factory=dict)
    alternatives_tried: list[str] = field(default_factory=list)
    search_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "strategy_used": self.strategy_used.value,
            "results_count": len(self.results),
            "total_matches": self.total_matches,
            "alternatives_tried": self.alternatives_tried,
            "search_confidence": self.search_confidence,
        }


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
