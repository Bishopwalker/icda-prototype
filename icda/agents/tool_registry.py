"""Dynamic Tool Registry for Query Agents.

Manages tool definitions and selection based on query intent and service availability.
Tools can be registered, conditionally enabled, and selected based on context.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .models import IntentResult, QueryDomain, QueryComplexity

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Categories of tools for organization."""
    CORE = "core"               # Always available
    SEARCH = "search"           # Search-related tools
    KNOWLEDGE = "knowledge"     # Knowledge base tools
    ADDRESS = "address"         # Address verification tools
    ANALYTICS = "analytics"     # Stats and analysis tools


@dataclass(slots=True)
class ToolSpec:
    """Specification for a single tool.

    Attributes:
        name: Unique tool identifier.
        description: Human-readable description for Nova.
        input_schema: JSON schema for tool parameters.
        category: Tool category for organization.
        domains: Query domains this tool is relevant for.
        min_complexity: Minimum query complexity to use this tool.
        conditions: List of condition names that must be true.
        executor: Function to execute the tool (name, params) -> result.
    """
    name: str
    description: str
    input_schema: dict[str, Any]
    category: ToolCategory = ToolCategory.CORE
    domains: list[QueryDomain] = field(default_factory=list)
    min_complexity: QueryComplexity = QueryComplexity.SIMPLE
    conditions: list[str] = field(default_factory=list)
    executor: Callable[[dict[str, Any]], dict[str, Any]] | None = None

    def to_bedrock_format(self) -> dict[str, Any]:
        """Convert to Bedrock toolSpec format."""
        return {
            "toolSpec": {
                "name": self.name,
                "description": self.description,
                "inputSchema": {"json": self.input_schema}
            }
        }


class ToolRegistry:
    """Dynamic registry for tool management.

    Supports:
    - Registration of new tools at runtime
    - Conditional tool availability based on service status
    - Intent-based tool selection
    - Graceful degradation when services unavailable
    """
    __slots__ = ("_tools", "_conditions", "_executors")

    def __init__(self):
        """Initialize empty registry."""
        self._tools: dict[str, ToolSpec] = {}
        self._conditions: dict[str, bool] = {}
        self._executors: dict[str, Callable] = {}

    def register(self, tool: ToolSpec) -> None:
        """Register a tool in the registry.

        Args:
            tool: ToolSpec to register.
        """
        self._tools[tool.name] = tool
        if tool.executor:
            self._executors[tool.name] = tool.executor
        logger.debug(f"Registered tool: {tool.name}")

    def register_executor(self, name: str, executor: Callable) -> None:
        """Register or update a tool executor.

        Args:
            name: Tool name.
            executor: Function to execute the tool.
        """
        self._executors[name] = executor

    def set_condition(self, name: str, value: bool) -> None:
        """Set a condition flag.

        Args:
            name: Condition name (e.g., 'opensearch_available').
            value: Whether the condition is met.
        """
        self._conditions[name] = value
        logger.debug(f"Condition {name} = {value}")

    def is_available(self, tool_name: str) -> bool:
        """Check if a tool is available based on its conditions.

        Args:
            tool_name: Name of the tool.

        Returns:
            True if all conditions are met.
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return False
        return all(self._conditions.get(c, False) for c in tool.conditions)

    def get_tool(self, name: str) -> ToolSpec | None:
        """Get a tool spec by name.

        Args:
            name: Tool name.

        Returns:
            ToolSpec or None if not found.
        """
        return self._tools.get(name)

    def get_tools_for_intent(self, intent: IntentResult) -> list[dict[str, Any]]:
        """Select tools appropriate for the given intent.

        Args:
            intent: Classification result from IntentAgent.

        Returns:
            List of tool specs in Bedrock format.
        """
        selected = []

        for tool in self._tools.values():
            # Check conditions are met
            if not self.is_available(tool.name):
                continue

            # Check complexity threshold
            complexity_order = [QueryComplexity.SIMPLE, QueryComplexity.MEDIUM, QueryComplexity.COMPLEX]
            if complexity_order.index(intent.complexity) < complexity_order.index(tool.min_complexity):
                continue

            # Core tools always included
            if tool.category == ToolCategory.CORE:
                selected.append(tool.to_bedrock_format())
                continue

            # Check domain relevance
            if tool.domains:
                if any(d in intent.domains for d in tool.domains):
                    selected.append(tool.to_bedrock_format())

        logger.debug(f"Selected {len(selected)} tools for intent {intent.primary_intent.value}")
        return selected

    def get_all_available_tools(self) -> list[dict[str, Any]]:
        """Get all currently available tools in Bedrock format.

        Returns:
            List of all available tool specs.
        """
        return [
            tool.to_bedrock_format()
            for tool in self._tools.values()
            if self.is_available(tool.name)
        ]

    def execute(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool by name.

        Args:
            name: Tool name.
            params: Tool parameters.

        Returns:
            Tool execution result.
        """
        executor = self._executors.get(name)
        if not executor:
            return {"success": False, "error": f"No executor for tool: {name}"}

        try:
            return executor(params)
        except Exception as e:
            logger.error(f"Tool {name} execution failed: {e}")
            return {"success": False, "error": str(e)}

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            List of tool names.
        """
        return list(self._tools.keys())

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Stats about registered tools and conditions.
        """
        available = sum(1 for t in self._tools if self.is_available(t))
        return {
            "total_tools": len(self._tools),
            "available_tools": available,
            "conditions": dict(self._conditions),
            "by_category": {
                cat.value: sum(1 for t in self._tools.values() if t.category == cat)
                for cat in ToolCategory
            }
        }


def create_default_registry(db, vector_index=None, knowledge=None, address_orchestrator=None) -> ToolRegistry:
    """Create a registry with default tools.

    Args:
        db: CustomerDB instance.
        vector_index: Optional VectorIndex for semantic search.
        knowledge: Optional KnowledgeManager for RAG.
        address_orchestrator: Optional address verification orchestrator.

    Returns:
        Configured ToolRegistry.
    """
    registry = ToolRegistry()

    # Set conditions based on available services
    registry.set_condition("always", True)
    registry.set_condition("opensearch_available", vector_index is not None and getattr(vector_index, "available", False))
    registry.set_condition("knowledge_available", knowledge is not None and getattr(knowledge, "available", False))
    registry.set_condition("address_available", address_orchestrator is not None)

    # ========================================================================
    # CORE TOOLS (always available)
    # ========================================================================
    registry.register(ToolSpec(
        name="lookup_crid",
        description="Look up a specific customer by their CRID (Customer Record ID). Use when user mentions a specific CRID or customer ID.",
        input_schema={
            "type": "object",
            "properties": {
                "crid": {"type": "string", "description": "The Customer Record ID (e.g., CRID-00001)"}
            },
            "required": ["crid"]
        },
        category=ToolCategory.CORE,
        domains=[QueryDomain.CUSTOMER],
        conditions=["always"],
        executor=lambda p: db.lookup(p.get("crid", ""))
    ))

    registry.register(ToolSpec(
        name="search_customers",
        description="Search for customers with flexible filters. Use when user asks about customers in a state/city, customers who moved, or general customer searches. Interpret informal language: 'Nevada folks'=state NV, 'high movers'=min_move_count 3+.",
        input_schema={
            "type": "object",
            "properties": {
                "state": {"type": "string", "description": "Two-letter state code (NV, CA, TX, etc)"},
                "city": {"type": "string", "description": "City name to filter by"},
                "min_move_count": {"type": "integer", "description": "Minimum number of moves"},
                "limit": {"type": "integer", "description": "Max results (default 10, max 100)"}
            }
        },
        category=ToolCategory.CORE,
        domains=[QueryDomain.CUSTOMER],
        conditions=["always"],
        executor=lambda p: db.search(
            state=p.get("state"),
            city=p.get("city"),
            min_moves=p.get("min_move_count"),
            limit=p.get("limit")
        )
    ))

    registry.register(ToolSpec(
        name="get_stats",
        description="Get overall customer statistics including counts by state. Use for 'how many customers', 'totals', 'breakdown', or aggregate questions.",
        input_schema={"type": "object", "properties": {}},
        category=ToolCategory.ANALYTICS,
        domains=[QueryDomain.STATS, QueryDomain.CUSTOMER],
        conditions=["always"],
        executor=lambda p: db.stats()
    ))

    # ========================================================================
    # SEARCH TOOLS (always available, different strategies)
    # ========================================================================
    registry.register(ToolSpec(
        name="fuzzy_search",
        description="Typo-tolerant fuzzy search for customer names or addresses. Use when query might have misspellings.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (name or address)"},
                "field": {"type": "string", "enum": ["name", "address", "city"], "description": "Field to search"},
                "limit": {"type": "integer", "description": "Max results (default 10)"}
            },
            "required": ["query"]
        },
        category=ToolCategory.SEARCH,
        domains=[QueryDomain.CUSTOMER],
        min_complexity=QueryComplexity.MEDIUM,
        conditions=["always"],
        executor=lambda p: db.autocomplete_fuzzy(
            p.get("field", "name"),
            p.get("query", ""),
            p.get("limit", 10)
        ) if hasattr(db, "autocomplete_fuzzy") else {"success": False, "error": "Fuzzy search not available"}
    ))

    # ========================================================================
    # SEMANTIC SEARCH TOOLS (require OpenSearch)
    # ========================================================================
    if vector_index:
        registry.register(ToolSpec(
            name="semantic_search",
            description="AI-powered semantic search for customers. Understands meaning, not just keywords. Use for complex natural language queries.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "state_filter": {"type": "string", "description": "Optional state filter"},
                    "limit": {"type": "integer", "description": "Max results (default 10)"}
                },
                "required": ["query"]
            },
            category=ToolCategory.SEARCH,
            domains=[QueryDomain.CUSTOMER],
            min_complexity=QueryComplexity.MEDIUM,
            conditions=["opensearch_available"],
            executor=lambda p: _sync_wrapper(vector_index.search_customers_semantic(
                p.get("query", ""),
                limit=p.get("limit", 10),
                state_filter=p.get("state_filter")
            )) if hasattr(vector_index, "search_customers_semantic") else {"success": False, "error": "Semantic search not available"}
        ))

        registry.register(ToolSpec(
            name="hybrid_search",
            description="Combined text and semantic search. Best for complex queries needing both exact matches and semantic understanding.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "state_filter": {"type": "string", "description": "Optional state filter"},
                    "limit": {"type": "integer", "description": "Max results (default 10)"}
                },
                "required": ["query"]
            },
            category=ToolCategory.SEARCH,
            domains=[QueryDomain.CUSTOMER],
            min_complexity=QueryComplexity.COMPLEX,
            conditions=["opensearch_available"],
            executor=lambda p: _sync_wrapper(vector_index.search_customers_hybrid(
                p.get("query", ""),
                limit=p.get("limit", 10),
                state_filter=p.get("state_filter")
            )) if hasattr(vector_index, "search_customers_hybrid") else {"success": False, "error": "Hybrid search not available"}
        ))

    # ========================================================================
    # KNOWLEDGE TOOLS (require knowledge base)
    # ========================================================================
    if knowledge:
        registry.register(ToolSpec(
            name="search_knowledge",
            description="Search the organizational knowledge base for policies, procedures, and documentation.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "category": {"type": "string", "description": "Optional category filter"},
                    "limit": {"type": "integer", "description": "Max results (default 5)"}
                },
                "required": ["query"]
            },
            category=ToolCategory.KNOWLEDGE,
            domains=[QueryDomain.KNOWLEDGE],
            conditions=["knowledge_available"],
            executor=lambda p: _sync_wrapper(knowledge.search(
                p.get("query", ""),
                category=p.get("category"),
                limit=p.get("limit", 5)
            )) if hasattr(knowledge, "search") else {"success": False, "error": "Knowledge search not available"}
        ))

    # ========================================================================
    # ADDRESS TOOLS (require address orchestrator)
    # ========================================================================
    if address_orchestrator:
        registry.register(ToolSpec(
            name="verify_address",
            description="Verify and normalize an address. Returns verified address components and confidence score.",
            input_schema={
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Raw address to verify"},
                    "state_hint": {"type": "string", "description": "Optional state hint"},
                    "city_hint": {"type": "string", "description": "Optional city hint"}
                },
                "required": ["address"]
            },
            category=ToolCategory.ADDRESS,
            domains=[QueryDomain.ADDRESS],
            conditions=["address_available"],
            executor=lambda p: _sync_wrapper(address_orchestrator.process(
                p.get("address", ""),
                hints={"state": p.get("state_hint"), "city": p.get("city_hint")}
            )) if address_orchestrator else {"success": False, "error": "Address verification not available"}
        ))

    logger.info(f"Tool registry initialized with {len(registry.list_tools())} tools")
    return registry


def _sync_wrapper(coro):
    """Wrapper to run async functions synchronously if needed.

    Args:
        coro: Coroutine to run.

    Returns:
        Result of the coroutine.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
