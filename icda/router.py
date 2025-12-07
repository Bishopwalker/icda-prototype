import json
from time import time

from .cache import RedisCache
from .database import CustomerDB
from .guardrails import Guardrails, GuardrailFlags
from .nova import NovaClient
from .vector_index import VectorIndex, RouteType


class Router:
    """Routes queries: Guardrails → Cache → Vector Route → DB/Nova"""
    __slots__ = ("cache", "vector_index", "db", "nova")

    def __init__(self, cache: RedisCache, vector_index: VectorIndex, db: CustomerDB, nova: NovaClient):
        self.cache = cache
        self.vector_index = vector_index
        self.db = db
        self.nova = nova

    async def route(self, query: str, bypass_cache: bool = False, guardrails: dict | None = None) -> dict:
        start = time()
        q = query.strip()

        # 1. Guardrails
        flags = GuardrailFlags(**guardrails) if guardrails else None
        if blocked := Guardrails.check(q, flags):
            return self._response(q, blocked, RouteType.CACHE_HIT, start, blocked=True)

        # 2. Cache check
        key = RedisCache.make_key(q)
        if not bypass_cache:
            if hit := await self.cache.get(key):
                data = json.loads(hit)
                return self._response(q, data["response"], RouteType.CACHE_HIT, start, cached=True)

        # 3. Vector routing
        route_type, metadata = await self.vector_index.find_route(q)

        # 4. Execute route
        if route_type == RouteType.DATABASE:
            tool = metadata.get("tool", "search_customers")
            result = self.db.execute(tool, q)
            if result["success"]:
                response = self._format_db_result(result, tool)
                await self.cache.set(key, json.dumps({"response": response}))
                return self._response(q, response, RouteType.DATABASE, start, tool=tool)
            route_type = RouteType.NOVA

        # 5. Nova for complex queries
        result = await self.nova.query(q)
        if result["success"]:
            await self.cache.set(key, json.dumps({"response": result["response"]}))
            return self._response(q, result["response"], RouteType.NOVA, start, tool=result.get("tool"))

        return self._response(q, result.get("error", "Unknown error"), RouteType.NOVA, start, success=False)

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
        return {
            "success": kwargs.get("success", True),
            "query": query,
            "response": response,
            "route": route.value,
            "cached": kwargs.get("cached", False),
            "blocked": kwargs.get("blocked", False),
            "tool": kwargs.get("tool"),
            "latency_ms": int((time() - start) * 1000)
        }
