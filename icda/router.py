import json
from time import time

from .cache import RedisCache
from .database import CustomerDB
from .guardrails import Guardrails, GuardrailFlags
from .nova import NovaClient
from .session import Session, SessionManager
from .vector_index import VectorIndex, RouteType


class Router:
    """Routes queries: Guardrails → Cache → Vector Route → DB/Nova with session context"""
    __slots__ = ("cache", "vector_index", "db", "nova", "sessions")

    def __init__(self, cache: RedisCache, vector_index: VectorIndex, db: CustomerDB, nova: NovaClient, sessions: SessionManager):
        self.cache = cache
        self.vector_index = vector_index
        self.db = db
        self.nova = nova
        self.sessions = sessions

    async def route(
        self,
        query: str,
        bypass_cache: bool = False,
        guardrails: dict | None = None,
        session_id: str | None = None
    ) -> dict:
        start = time()
        q = query.strip()

        # Get or create session
        session = await self.sessions.get(session_id)

        # 1. Guardrails
        flags = GuardrailFlags(**guardrails) if guardrails else None
        if blocked := Guardrails.check(q, flags):
            return self._response(q, blocked, RouteType.CACHE_HIT, start, blocked=True, session_id=session.session_id)

        # 2. Cache check (skip for conversational context - cache is for isolated queries)
        key = RedisCache.make_key(q)
        if not bypass_cache and not session.messages:
            if hit := await self.cache.get(key):
                data = json.loads(hit)
                return self._response(q, data["response"], RouteType.CACHE_HIT, start, cached=True, session_id=session.session_id)

        # 3. Vector routing
        route_type, metadata = await self.vector_index.find_route(q)

        # 4. Execute route
        if route_type == RouteType.DATABASE:
            tool = metadata.get("tool", "search_customers")
            result = self.db.execute(tool, q)
            if result["success"]:
                response = self._format_db_result(result, tool)
                # Store in session
                session.add_message("user", q)
                session.add_message("assistant", response)
                await self.sessions.save(session)
                # Cache only if no prior context
                if len(session.messages) <= 2:
                    await self.cache.set(key, json.dumps({"response": response}))
                return self._response(q, response, RouteType.DATABASE, start, tool=tool, session_id=session.session_id)
            route_type = RouteType.NOVA

        # 5. Nova for complex queries - uses 8-agent pipeline when available
        # The orchestrator handles:
        # - Intent classification
        # - Dynamic tool selection
        # - Parallel search + knowledge retrieval
        # - Quality enforcement and PII redaction
        history = session.get_history(max_messages=20) if session.messages else None

        # RAG context is now handled by the KnowledgeAgent in orchestrated mode
        # But we still provide fallback RAG for simple mode
        context = None
        if not self.nova.orchestrator:
            rag_result = await self.vector_index.search_customers_semantic(q, limit=5)
            if rag_result["success"] and rag_result["count"] > 0:
                customers = rag_result["data"]
                context_lines = ["Found relevant customer records:"]
                for c in customers:
                    context_lines.append(f"- {c['name']} (CRID: {c['crid']}): {c['city']}, {c['state']}, {c['move_count']} moves. Status: {c['status']}")
                context = "\n".join(context_lines)

        # Pass session_id for orchestrator context tracking
        result = await self.nova.query(
            q,
            history=history,
            context=context,
            session_id=session.session_id,
        )

        if result["success"]:
            response = result["response"]
            # Update session
            session.add_message("user", q)
            session.add_message("assistant", response)
            await self.sessions.save(session)
            # Cache only standalone queries
            if len(session.messages) <= 2:
                await self.cache.set(key, json.dumps({"response": response}))
            return self._response(
                q,
                response,
                RouteType.NOVA,
                start,
                tool=result.get("tool"),
                session_id=session.session_id,
                quality_score=result.get("quality_score"),
                nova_route=result.get("route"),
            )

        return self._response(q, result.get("error", "Unknown error"), RouteType.NOVA, start, success=False, session_id=session.session_id)

    def _format_db_result(self, result: dict, tool: str) -> str:
        match tool:
            case "lookup_crid":
                c = result["data"]
                return f"Customer {c['name']} ({c['crid']}): {c['city']}, {c['state']}. Moved {c['move_count']} times."
            case "search_customers":
                total = result["total"]
                customers = result["data"]
                lines = [f"Found {total} customers:"]
                for c in customers:
                    lines.append(f"- {c['name']} ({c['crid']}): {c['city']}, {c['state']} - {c['move_count']} moves")
                return "\n".join(lines)
            case "get_stats":
                stats = result["data"]
                sorted_stats = sorted(stats.items(), key=lambda x: -x[1])
                lines = [f"Customer count by state (Total: {result['total']}):"]
                for state, count in sorted_stats:
                    lines.append(f"- {state}: {count}")
                return "\n".join(lines)
        return json.dumps(result)

    def _response(self, query: str, response: str, route: RouteType, start: float, **kwargs) -> dict:
        """Build response dict with optional orchestrator metadata.

        Args:
            query: Original query.
            response: Response text.
            route: Route type taken.
            start: Start time for latency calculation.
            **kwargs: Additional response fields.

        Returns:
            Response dict.
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
        }

        # Add orchestrator metadata if available
        if kwargs.get("quality_score") is not None:
            result["quality_score"] = kwargs["quality_score"]
        if kwargs.get("nova_route"):
            result["nova_route"] = kwargs["nova_route"]

        return result
