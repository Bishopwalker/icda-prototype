"""Query Orchestrator - 8-Agent Query Processing Pipeline.

Coordinates the full query processing pipeline:
1. IntentAgent -> Classify query intent
2. ContextAgent -> Extract session context
3. ParserAgent -> Normalize and extract entities
4. ResolverAgent -> Resolve references
5. SearchAgent -> Execute search (parallel with 6)
6. KnowledgeAgent -> RAG retrieval (parallel with 5)
7. NovaAgent -> AI response generation
8. EnforcerAgent -> Quality gates and validation

Follows the enforcer pattern from address verification orchestrator.
"""

import asyncio
import logging
import time
from typing import Any

from .models import (
    IntentResult,
    QueryContext,
    ParsedQuery,
    ResolvedQuery,
    SearchResult,
    KnowledgeContext,
    NovaResponse,
    EnforcedResponse,
    PipelineTrace,
    PipelineStage,
    QueryResult,
    SearchStrategy,
    TokenUsage,
    PaginationInfo,
    ModelRoutingDecision,
)
from .tool_registry import ToolRegistry, create_default_registry
from .model_router import ModelRouter
from .intent_agent import IntentAgent
from .context_agent import ContextAgent
from .parser_agent import ParserAgent
from .resolver_agent import ResolverAgent
from .search_agent import SearchAgent
from .knowledge_agent import KnowledgeAgent
from .nova_agent import NovaAgent
from .enforcer_agent import EnforcerAgent

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    """Orchestrates the 8-agent query processing pipeline.

    Coordinates data flow between agents, handles parallel execution,
    and provides comprehensive tracing for debugging.

    Enhanced features:
    - Model routing (Micro/Lite/Pro) based on complexity and confidence
    - Token usage tracking across pipeline stages
    - Pagination for large result sets with download tokens
    - Confidence tracking for all agents
    """
    __slots__ = (
        "_intent_agent",
        "_context_agent",
        "_parser_agent",
        "_resolver_agent",
        "_search_agent",
        "_knowledge_agent",
        "_nova_agent",
        "_enforcer_agent",
        "_tool_registry",
        "_session_store",
        "_config",
        "_model_router",
        "_download_manager",
    )

    def __init__(
        self,
        db,
        region: str = "us-west-2",
        model: str = "us.amazon.nova-micro-v1:0",
        vector_index=None,
        knowledge=None,
        address_orchestrator=None,
        session_store=None,
        guardrails=None,
        gemini_enforcer=None,
        config: dict[str, Any] | None = None,
        download_manager=None,
    ):
        """Initialize QueryOrchestrator with all agents.

        Args:
            db: CustomerDB instance.
            region: AWS region for Bedrock.
            model: Bedrock model ID (default/micro model).
            vector_index: Optional VectorIndex for semantic search.
            knowledge: Optional KnowledgeManager for RAG.
            address_orchestrator: Optional address verification orchestrator.
            session_store: Optional session store for context.
            guardrails: Optional Guardrails for PII filtering.
            gemini_enforcer: Optional GeminiEnforcer for AI-powered validation.
            config: Optional configuration overrides.
            download_manager: Optional DownloadTokenManager for pagination.
        """
        self._config = config or {}
        self._session_store = session_store
        self._download_manager = download_manager

        # Create model router with configuration
        lite_model = self._config.get("nova_lite_model", "us.amazon.nova-lite-v1:0")
        pro_model = self._config.get("nova_pro_model", "us.amazon.nova-pro-v1:0")
        threshold = self._config.get("model_routing_threshold", 0.6)

        self._model_router = ModelRouter(
            micro_model=model,
            lite_model=lite_model,
            pro_model=pro_model,
            confidence_threshold=threshold,
        )

        # Create tool registry with available services
        self._tool_registry = create_default_registry(
            db=db,
            vector_index=vector_index,
            knowledge=knowledge,
            address_orchestrator=address_orchestrator,
        )

        # Initialize all 7 core agents + 1 Gemini-powered enforcer
        # Each agent receives ONLY the context it needs (enforcer pattern)
        self._intent_agent = IntentAgent()
        self._context_agent = ContextAgent(session_manager=session_store)
        self._parser_agent = ParserAgent()
        self._resolver_agent = ResolverAgent(db=db, vector_index=vector_index)
        self._search_agent = SearchAgent(db=db, vector_index=vector_index)
        self._knowledge_agent = KnowledgeAgent(knowledge=knowledge)
        self._nova_agent = NovaAgent(
            region=region,
            model=model,
            tool_registry=self._tool_registry,
        )
        self._enforcer_agent = EnforcerAgent(
            guardrails=guardrails,
            gemini_enforcer=gemini_enforcer,
        )

        # Log initialization with Gemini status
        gemini_status = "enabled" if (gemini_enforcer and gemini_enforcer.available) else "disabled"
        logger.info(
            f"QueryOrchestrator initialized: {len(self._tool_registry.list_tools())} tools, Gemini enforcer: {gemini_status}"
        )
        logger.info(f"Model routing: micro={model}, lite={lite_model}, pro={pro_model}, threshold={threshold}")

    @property
    def available(self) -> bool:
        """Check if orchestrator is operational."""
        # At minimum, we need intent and search agents
        return self._intent_agent.available and self._search_agent.available

    async def process(
        self,
        query: str,
        session_id: str | None = None,
        trace_enabled: bool = True,
    ) -> QueryResult:
        """Process a query through the 8-agent pipeline.

        Args:
            query: User query string.
            session_id: Optional session ID for context.
            trace_enabled: Whether to capture detailed trace.

        Returns:
            QueryResult with response and metadata.
        """
        start_time = time.time()
        trace = PipelineTrace() if trace_enabled else None

        try:
            # Stage 1: Intent Classification
            intent = await self._run_stage(
                "intent",
                lambda: self._intent_agent.classify(query),
                trace,
            )

            # Stage 2: Context Extraction
            context = await self._run_stage(
                "context",
                lambda: self._context_agent.extract(
                    query=query,
                    session_id=session_id,
                    intent=intent,
                ),
                trace,
            )

            # Stage 3: Query Parsing
            parsed = await self._run_stage(
                "parser",
                lambda: self._parser_agent.parse(
                    query=query,
                    intent=intent,
                    context=context,
                ),
                trace,
            )

            # Stage 4: Entity Resolution
            resolved = await self._run_stage(
                "resolver",
                lambda: self._resolver_agent.resolve(
                    parsed=parsed,
                    context=context,
                ),
                trace,
            )

            # Stage 5 & 6: Search + Knowledge (parallel)
            search_result, knowledge = await self._run_parallel_stages(
                search_coro=self._search_agent.search(
                    resolved=resolved,
                    parsed=parsed,
                    intent=intent,
                ),
                knowledge_coro=self._knowledge_agent.retrieve(
                    query=query,
                    intent=intent,
                    parsed=parsed,
                ),
                trace=trace,
            )

            # Collect confidences from all agents for model routing
            agent_confidences = [
                intent.confidence,
                context.context_confidence,
                resolved.resolution_confidence,
                search_result.search_confidence,
                knowledge.rag_confidence,
            ]

            # Stage 7: Nova AI Generation (with model routing)
            # Model router decides Micro/Lite/Pro based on complexity and confidence
            routing_decision = self._model_router.route(
                intent=intent,
                parsed=parsed,
                search_result=search_result,
                agent_confidences=agent_confidences,
            )

            # Record routing decision in trace
            if trace:
                trace.model_routing_decision = routing_decision

            nova_response = await self._run_stage(
                "nova",
                lambda: self._nova_agent.generate(
                    query=query,
                    search_result=search_result,
                    knowledge=knowledge,
                    context=context,
                    intent=intent,
                    model_override=routing_decision.model_id,
                ),
                trace,
            )

            # Stage 8: Enforcement
            enforced = await self._run_stage(
                "enforcer",
                lambda: self._enforcer_agent.enforce(
                    nova_response=nova_response,
                    query=query,
                    intent=intent,
                    parsed=parsed,
                ),
                trace,
            )

            # Calculate total time
            total_ms = int((time.time() - start_time) * 1000)
            if trace:
                trace.total_time_ms = total_ms
                trace.success = True
                # Add token usage to trace from Nova response
                if nova_response.token_usage:
                    trace.total_token_usage = nova_response.token_usage

            # Store context for follow-up queries
            if session_id and self._session_store:
                await self._store_context(
                    session_id=session_id,
                    query=query,
                    response=enforced.final_response,
                    intent=intent,
                    search_result=search_result,
                )

            # Apply pagination if download_manager available
            pagination = None
            preview_results = None
            full_results = search_result.results

            if self._download_manager and search_result.total_matches > 0:
                preview_results, pagination_dict = self._download_manager.create_download_token(
                    results=full_results,
                    query=query,
                )
                pagination = PaginationInfo(
                    total_count=pagination_dict["total_count"],
                    returned_count=pagination_dict["returned_count"],
                    has_more=pagination_dict["has_more"],
                    suggest_download=pagination_dict["suggest_download"],
                    download_token=pagination_dict.get("download_token"),
                    preview_size=pagination_dict.get("preview_size", 15),
                )

            return QueryResult(
                success=True,
                response=enforced.final_response,
                route=self._determine_route(nova_response, enforced),
                tools_used=nova_response.tools_used,
                quality_score=enforced.quality_score,
                latency_ms=total_ms,
                trace=trace,
                metadata={
                    "intent": intent.to_dict(),
                    "search_strategy": search_result.strategy_used.value,
                    "status": enforced.status.value,
                    "gates_passed": len(enforced.gates_passed),
                    "gates_failed": len(enforced.gates_failed),
                    "model_routing": routing_decision.to_dict(),
                },
                token_usage=nova_response.token_usage,
                pagination=pagination,
                model_used=nova_response.model_used,
                results=preview_results if preview_results else full_results,
            )

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            total_ms = int((time.time() - start_time) * 1000)

            if trace:
                trace.total_time_ms = total_ms
                trace.success = False

            # Return graceful fallback
            return QueryResult(
                success=False,
                response=f"I encountered an error processing your query. Please try again or rephrase your question.",
                route="error",
                tools_used=[],
                quality_score=0.0,
                latency_ms=total_ms,
                trace=trace,
                metadata={"error": str(e)},
            )

    async def _run_stage(
        self,
        name: str,
        coro_factory,
        trace: PipelineTrace | None,
    ):
        """Run a single pipeline stage with timing.

        Args:
            name: Stage name.
            coro_factory: Factory function that returns coroutine.
            trace: Optional trace to record stage.

        Returns:
            Stage output.
        """
        start = time.time()
        try:
            result = await coro_factory()
            elapsed_ms = int((time.time() - start) * 1000)

            if trace:
                # Extract confidence from result if available
                confidence = None
                token_usage = None

                if hasattr(result, "confidence"):
                    confidence = result.confidence
                elif hasattr(result, "ai_confidence"):
                    confidence = result.ai_confidence
                elif hasattr(result, "search_confidence"):
                    confidence = result.search_confidence
                elif hasattr(result, "rag_confidence"):
                    confidence = result.rag_confidence
                elif hasattr(result, "resolution_confidence"):
                    confidence = result.resolution_confidence
                elif hasattr(result, "context_confidence"):
                    confidence = result.context_confidence
                elif hasattr(result, "quality_score"):
                    confidence = result.quality_score

                # Extract token usage from Nova stage
                if hasattr(result, "token_usage") and result.token_usage:
                    token_usage = result.token_usage

                # Use the add_stage method to track confidence and aggregate tokens
                trace.add_stage(
                    agent=name,
                    output=result.to_dict() if hasattr(result, "to_dict") else {},
                    time_ms=elapsed_ms,
                    success=True,
                    confidence=confidence,
                    token_usage=token_usage,
                )

            logger.debug(f"Stage {name} completed in {elapsed_ms}ms")
            return result

        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.error(f"Stage {name} failed: {e}")

            if trace:
                trace.add_stage(
                    agent=name,
                    output={},
                    time_ms=elapsed_ms,
                    success=False,
                    error=str(e),
                )
            raise

    async def _run_parallel_stages(
        self,
        search_coro,
        knowledge_coro,
        trace: PipelineTrace | None,
    ) -> tuple[SearchResult, KnowledgeContext]:
        """Run search and knowledge stages in parallel.

        Args:
            search_coro: Search agent coroutine.
            knowledge_coro: Knowledge agent coroutine.
            trace: Optional trace to record stages.

        Returns:
            Tuple of (SearchResult, KnowledgeContext).
        """
        start = time.time()

        # Run both in parallel
        search_task = asyncio.create_task(search_coro)
        knowledge_task = asyncio.create_task(knowledge_coro)

        # Wait for both, handling errors gracefully
        search_result = None
        knowledge_result = None
        search_error = None
        knowledge_error = None

        try:
            search_result = await search_task
        except Exception as e:
            search_error = str(e)
            logger.warning(f"Search stage failed: {e}")
            search_result = SearchResult(
                strategy_used=SearchStrategy.KEYWORD,
                results=[],
                total_matches=0,
                search_confidence=0.0,
            )

        try:
            knowledge_result = await knowledge_task
        except Exception as e:
            knowledge_error = str(e)
            logger.warning(f"Knowledge stage failed: {e}")
            knowledge_result = KnowledgeContext(
                relevant_chunks=[],
                total_chunks_found=0,
                rag_confidence=0.0,
            )

        elapsed_ms = int((time.time() - start) * 1000)

        if trace:
            # Record search stage with confidence
            trace.add_stage(
                agent="search",
                output=search_result.to_dict(),
                time_ms=elapsed_ms,
                success=search_error is None,
                error=search_error,
                confidence=search_result.search_confidence if search_error is None else None,
            )
            # Record knowledge stage with confidence
            trace.add_stage(
                agent="knowledge",
                output=knowledge_result.to_dict(),
                time_ms=elapsed_ms,
                success=knowledge_error is None,
                error=knowledge_error,
                confidence=knowledge_result.rag_confidence if knowledge_error is None else None,
            )

        logger.debug(f"Parallel stages completed in {elapsed_ms}ms")
        return search_result, knowledge_result

    async def _store_context(
        self,
        session_id: str,
        query: str,
        response: str,
        intent: IntentResult,
        search_result: SearchResult,
    ) -> None:
        """Store query context for follow-up queries.

        Args:
            session_id: Session identifier.
            query: Original query.
            response: Generated response.
            intent: Intent classification.
            search_result: Search results.
        """
        if not self._session_store:
            return

        try:
            # Add to conversation history
            if hasattr(self._session_store, "add_message"):
                await self._session_store.add_message(
                    session_id,
                    {"role": "user", "content": [{"text": query}]},
                )
                await self._session_store.add_message(
                    session_id,
                    {"role": "assistant", "content": [{"text": response}]},
                )

            # Store last results for follow-up reference
            if hasattr(self._session_store, "set"):
                await self._session_store.set(
                    f"{session_id}:last_results",
                    {
                        "query": query,
                        "results": search_result.results[:10],
                        "intent": intent.primary_intent.value,
                    },
                    ttl=3600,  # 1 hour
                )

        except Exception as e:
            logger.warning(f"Failed to store context: {e}")

    def _determine_route(
        self,
        nova_response: NovaResponse,
        enforced: EnforcedResponse,
    ) -> str:
        """Determine which route was taken for the response.

        Args:
            nova_response: Response from Nova agent.
            enforced: Enforced response.

        Returns:
            Route identifier string.
        """
        if nova_response.model_used == "fallback":
            return "fallback"
        if nova_response.tools_used:
            return "nova_with_tools"
        return "nova"

    def get_stats(self) -> dict[str, Any]:
        """Get orchestrator statistics.

        Returns:
            Dict with agent and tool stats.
        """
        return {
            "agents": {
                "intent": self._intent_agent.available,
                "context": self._context_agent.available,
                "parser": self._parser_agent.available,
                "resolver": self._resolver_agent.available,
                "search": self._search_agent.available,
                "knowledge": self._knowledge_agent.available,
                "nova": self._nova_agent.available,
                "enforcer": self._enforcer_agent.available,
            },
            "tools": self._tool_registry.get_stats(),
        }


def create_query_orchestrator(
    db,
    region: str = "us-west-2",
    model: str = "us.amazon.nova-micro-v1:0",
    vector_index=None,
    knowledge=None,
    address_orchestrator=None,
    session_store=None,
    guardrails=None,
    gemini_enforcer=None,
    config: dict[str, Any] | None = None,
    download_manager=None,
) -> QueryOrchestrator:
    """Factory function to create a QueryOrchestrator.

    Args:
        db: CustomerDB instance.
        region: AWS region for Bedrock.
        model: Bedrock model ID (default/micro model).
        vector_index: Optional VectorIndex for semantic search.
        knowledge: Optional KnowledgeManager for RAG.
        address_orchestrator: Optional address verification orchestrator.
        session_store: Optional session store for context.
        guardrails: Optional Guardrails for PII filtering.
        gemini_enforcer: Optional GeminiEnforcer for AI-powered validation.
        config: Optional configuration dict for model routing settings.
        download_manager: Optional DownloadTokenManager for pagination.

    Returns:
        Configured QueryOrchestrator instance.
    """
    return QueryOrchestrator(
        db=db,
        region=region,
        model=model,
        vector_index=vector_index,
        knowledge=knowledge,
        address_orchestrator=address_orchestrator,
        session_store=session_store,
        guardrails=guardrails,
        gemini_enforcer=gemini_enforcer,
        config=config,
        download_manager=download_manager,
    )
