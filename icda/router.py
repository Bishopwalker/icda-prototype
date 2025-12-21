"""Simplified Router - Thin gateway to 8-agent orchestrator.

Refactored from dual-path (DB vs Nova) to single-path orchestrator.
All query processing now goes through the QueryOrchestrator pipeline.

Pipeline:
1. Parallel: session fetch + cache check
2. Guardrails check (fast, sync)
3. Cache hit → return early
4. Everything else → orchestrator
5. Update session + cache
"""

import asyncio
import json
from time import time

from .cache import RedisCache
from .database import CustomerDB
from .guardrails import Guardrails, GuardrailFlags
from .nova import NovaClient
from .session import Session, SessionManager
from .vector_index import VectorIndex, RouteType


class Router:
    """Thin gateway that delegates all queries to the orchestrator.

    Previous design had two paths:
    - DATABASE: Direct db.execute() with basic formatting
    - NOVA: Full 8-agent orchestrator pipeline

    New design:
    - ALL queries go through orchestrator (consistent quality gates)
    - Router only handles: session, cache, guardrails
    - Orchestrator handles: intent, search, knowledge, AI, enforcement

    IMPORTANT: Guardrails-aware caching:
    - When guardrails are OFF (all disabled), cache is SKIPPED entirely
    - Different guardrail states = different expected responses
    - Only cache responses when guardrails are active
    """
    __slots__ = ("cache", "vector_index", "db", "nova", "sessions")

    def __init__(
        self,
        cache: RedisCache,
        vector_index: VectorIndex,
        db: CustomerDB,
        nova: NovaClient,
        sessions: SessionManager,
    ):
        self.cache = cache
        self.vector_index = vector_index  # Kept for semantic search endpoints
        self.db = db  # Kept for autocomplete endpoints
        self.nova = nova
        self.sessions = sessions

    def _are_guardrails_active(self, flags: GuardrailFlags | None) -> bool:
        """Check if any guardrails are enabled.

        Args:
            flags: Guardrail flags (None = all enabled by default).

        Returns:
            True if at least one guardrail is active.
        """
        if flags is None:
            return True  # Default: all guardrails enabled
        return any([
            flags.pii,
            flags.financial,
            flags.credentials,
            flags.offtopic,
        ])

    async def route(
        self,
        query: str,
        bypass_cache: bool = False,
        guardrails: dict | None = None,
        session_id: str | None = None,
    ) -> dict:
        """Route query through the orchestrator pipeline.

        All queries now go through the 8-agent pipeline for consistent:
        - Intent classification
        - Quality enforcement
        - PII redaction
        - Response formatting

        Args:
            query: User query string.
            bypass_cache: Skip cache lookup.
            guardrails: Guardrail flag overrides.
            session_id: Session ID for conversation context.

        Returns:
            Response dict with query result and metadata.
        """
        start = time()
        q = query.strip()

        # Determine guardrails state early (needed for cache decisions)
        flags = GuardrailFlags(**guardrails) if guardrails else None
        guardrails_active = self._are_guardrails_active(flags)

        # 1. PARALLEL: Session fetch + Cache check
        # This eliminates sequential bottleneck from previous design
        session_task = asyncio.create_task(self.sessions.get(session_id))
        
        # Only check cache if conditions allow
        key = RedisCache.make_key(q)
        cache_task = None
        if not bypass_cache and guardrails_active:
            cache_task = asyncio.create_task(self.cache.get(key))

        # Await session (always needed)
        session = await session_task

        # 2. GUARDRAILS CHECK (fast, sync - no await needed)
        if guardrails_active:
            if blocked := Guardrails.check(q, flags):
                return self._response(
                    q, blocked, RouteType.CACHE_HIT, start,
                    blocked=True,
                    session_id=session.session_id,
                    guardrails_active=guardrails_active,
                    guardrails_bypassed=False,
                )

        # 3. CACHE CHECK - await parallel task if started
        # Skip cache if: bypass requested, guardrails off, or session has context
        should_use_cache = (
            cache_task is not None and
            not session.messages  # Don't use cache for multi-turn conversations
        )

        if should_use_cache:
            cached = await cache_task
            if cached:
                data = json.loads(cached)
                return self._response(
                    q, data["response"], RouteType.CACHE_HIT, start,
                    cached=True,
                    session_id=session.session_id,
                    guardrails_active=guardrails_active,
                    guardrails_bypassed=False,
                )
        elif cache_task:
            # Cancel unused cache task
            cache_task.cancel()
            try:
                await cache_task
            except asyncio.CancelledError:
                pass

        # 4. ORCHESTRATOR - All queries go through 8-agent pipeline
        # Previous design had two paths (DB vs Nova) causing inconsistent behavior
        # Now everything gets: intent classification, quality gates, enforcement
        result = await self.nova.query(
            q,
            session_id=session.session_id,
        )

        if result["success"]:
            response = result["response"]

            # 5. SESSION UPDATE
            session.add_message("user", q)
            session.add_message("assistant", response)
            await self.sessions.save(session)

            # 6. CACHE UPDATE
            # Only cache standalone queries when guardrails active
            should_cache = len(session.messages) <= 2 and guardrails_active
            if should_cache:
                await self.cache.set(key, json.dumps({"response": response}))

            # Map orchestrator route to RouteType
            route_type = self._map_route(result.get("route", "nova"))

            return self._response(
                q,
                response,
                route_type,
                start,
                tool=result.get("tool"),
                session_id=session.session_id,
                quality_score=result.get("quality_score"),
                nova_route=result.get("route"),
                guardrails_active=guardrails_active,
                guardrails_bypassed=not guardrails_active,
                # Enhanced pipeline data from orchestrator
                token_usage=result.get("token_usage"),
                trace=result.get("trace"),
                model_used=result.get("model_used"),
                pagination=result.get("pagination"),
                results=result.get("results"),
            )

        # Error case
        return self._response(
            q, result.get("error", "Unknown error"), RouteType.NOVA, start,
            success=False,
            session_id=session.session_id,
            guardrails_active=guardrails_active,
            guardrails_bypassed=not guardrails_active,
        )

    def _map_route(self, orchestrator_route: str) -> RouteType:
        """Map orchestrator route string to RouteType enum.

        Orchestrator returns: "nova", "nova_with_tools", "fallback", "error"
        Router expects: RouteType enum for backward compatibility.

        Args:
            orchestrator_route: Route string from orchestrator.

        Returns:
            RouteType enum value.
        """
        # The orchestrator's SearchAgent and NovaAgent handle both DB and AI queries
        # Map tool-based routes to DATABASE for metrics compatibility
        if orchestrator_route in ("nova_with_tools", "database"):
            return RouteType.DATABASE
        return RouteType.NOVA

    def _response(
        self,
        query: str,
        response: str,
        route: RouteType,
        start: float,
        **kwargs,
    ) -> dict:
        """Build response dict with optional orchestrator metadata.

        Maintains backward compatibility with frontend expectations.

        Args:
            query: Original query.
            response: Response text.
            route: Route type taken.
            start: Start time for latency calculation.
            **kwargs: Additional response fields including:
                - success: Whether query succeeded.
                - cached: Whether response was from cache.
                - blocked: Whether guardrails blocked.
                - tool: Tool used (if any).
                - session_id: Session identifier.
                - quality_score: Quality score from enforcer.
                - nova_route: Sub-route within Nova.
                - guardrails_active: Whether guardrails were active.
                - guardrails_bypassed: Whether guardrails were bypassed.
                - token_usage: Token usage stats.
                - trace: Pipeline trace.
                - model_used: Nova model used.
                - pagination: Pagination info.
                - results: Raw search results.

        Returns:
            Response dict with all available metadata.
        """
        result = {
            "success": kwargs.get("success", True),
            "query": query,
            "response": response,
            "route": route.value,
            "cached": kwargs.get("cached", False),
            "blocked": kwargs.get("blocked", False),
            "tool": kwargs.get("tool"),
            "latency_ms": int((time() - start) * 1000),
            "session_id": kwargs.get("session_id"),
            # Guardrails state
            "guardrails_active": kwargs.get("guardrails_active", True),
            "guardrails_bypassed": kwargs.get("guardrails_bypassed", False),
        }

        # Add orchestrator metadata if available
        if kwargs.get("quality_score") is not None:
            result["quality_score"] = kwargs["quality_score"]
        if kwargs.get("nova_route"):
            result["nova_route"] = kwargs["nova_route"]

        # Enhanced pipeline data
        if kwargs.get("token_usage") is not None:
            token_usage = kwargs["token_usage"]
            # Convert to dict if it's a TokenUsage object
            result["token_usage"] = (
                token_usage.to_dict() if hasattr(token_usage, "to_dict") else token_usage
            )

        if kwargs.get("trace") is not None:
            trace = kwargs["trace"]
            # Convert to dict if it's a PipelineTrace object
            result["trace"] = trace.to_dict() if hasattr(trace, "to_dict") else trace

        if kwargs.get("model_used"):
            result["model_used"] = kwargs["model_used"]

        if kwargs.get("pagination") is not None:
            pagination = kwargs["pagination"]
            # Convert to dict if it's a PaginationInfo object
            result["pagination"] = (
                pagination.to_dict() if hasattr(pagination, "to_dict") else pagination
            )

        if kwargs.get("results") is not None:
            result["results"] = kwargs["results"]

        return result
