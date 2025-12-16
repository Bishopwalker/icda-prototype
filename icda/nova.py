import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .database import CustomerDB
from .agents import QueryOrchestrator, create_query_orchestrator

logger = logging.getLogger(__name__)


class NovaClient:
    """
    Amazon Bedrock Nova client for AI-powered queries.
    Gracefully handles missing AWS credentials.

    Supports two modes:
    1. Simple mode: Direct tool calling with 3 static tools
    2. Orchestrated mode: 8-agent pipeline with dynamic tools

    The orchestrated mode is enabled by default when available.
    """
    __slots__ = ("client", "model", "available", "db", "_orchestrator", "_use_orchestrator")

    _PROMPT = """You are ICDA, a customer data assistant. Be concise and helpful.

QUERY INTERPRETATION:
- Interpret queries flexibly, not literally
- State names → abbreviations (Nevada=NV, California=CA, Texas=TX)
- "high movers"/"frequent movers" → min_move_count 3+
- Use reasonable defaults (limit=10 for searches)
- Never provide SSN, financial, or health info
- Use conversation history for context"""

    TOOLS = [
        {"toolSpec": {"name": "lookup_crid", "description": "Look up a specific customer by their CRID (Customer Record ID). Use when user mentions a specific CRID or customer ID.",
            "inputSchema": {"json": {"type": "object", "properties": {"crid": {"type": "string", "description": "The Customer Record ID (e.g., CRID-00001)"}}, "required": ["crid"]}}}},
        {"toolSpec": {"name": "search_customers", "description": "Search for customers with flexible filters. Use when user asks about customers in a state/city, customers who moved, or general customer searches. Interpret informal language: 'Nevada folks'=state NV, 'high movers'=min_move_count 3+, 'California customers'=state CA.",
            "inputSchema": {"json": {"type": "object", "properties": {
                "state": {"type": "string", "description": "Two-letter state code (NV, CA, TX, NY, FL, etc). Convert state names to codes."},
                "city": {"type": "string", "description": "City name to filter by"},
                "min_move_count": {"type": "integer", "description": "Minimum number of moves. Use 2-3 for 'frequent movers', 5+ for 'high movers'"},
                "limit": {"type": "integer", "description": "Max results to return (default 10, max 100)"}}}}}},
        {"toolSpec": {"name": "get_stats", "description": "Get overall customer statistics including counts by state. Use for questions like 'how many customers', 'totals', 'breakdown', or any aggregate data questions.",
            "inputSchema": {"json": {"type": "object", "properties": {}}}}}
    ]

    def __init__(
        self,
        region: str,
        model: str,
        db: CustomerDB,
        vector_index=None,
        knowledge=None,
        address_orchestrator=None,
        session_store=None,
        guardrails=None,
        use_orchestrator: bool = True,
    ):
        """Initialize NovaClient with optional 8-agent pipeline.

        Args:
            region: AWS region for Bedrock.
            model: Bedrock model ID.
            db: CustomerDB instance.
            vector_index: Optional VectorIndex for semantic search.
            knowledge: Optional KnowledgeManager for RAG.
            address_orchestrator: Optional address verification orchestrator.
            session_store: Optional session store for context.
            guardrails: Optional Guardrails for PII filtering.
            use_orchestrator: Whether to use 8-agent pipeline (default True).
        """
        self.model = model
        self.db = db
        self.client = None
        self.available = False
        self._orchestrator = None
        self._use_orchestrator = use_orchestrator

        # Check if AWS credentials are configured
        if not os.environ.get("AWS_ACCESS_KEY_ID") and not os.environ.get("AWS_PROFILE"):
            logger.info("Nova: No AWS credentials - AI features disabled (LITE MODE)")
            return

        try:
            self.client = boto3.client("bedrock-runtime", region_name=region)
            self.available = True
            logger.info(f"Nova: Connected ({model})")

            # Initialize 8-agent orchestrator if enabled
            if use_orchestrator:
                try:
                    self._orchestrator = create_query_orchestrator(
                        db=db,
                        region=region,
                        model=model,
                        vector_index=vector_index,
                        knowledge=knowledge,
                        address_orchestrator=address_orchestrator,
                        session_store=session_store,
                        guardrails=guardrails,
                    )
                    logger.info("Nova: 8-agent orchestrator enabled")
                except Exception as e:
                    logger.warning(f"Nova: Orchestrator init failed, using simple mode - {e}")
                    self._orchestrator = None

        except NoCredentialsError:
            logger.warning("Nova: AWS credentials not found - AI features disabled")
        except Exception as e:
            logger.error(f"Nova: Init failed - {e}")

    def _converse(self, messages: list, context: str | None = None) -> dict:
        system_prompts = [{"text": self._PROMPT}]
        if context:
            system_prompts.append({"text": f"\n\nRELEVANT DATA CONTEXT:\n{context}"})

        return self.client.converse(
            modelId=self.model,
            messages=messages,
            system=system_prompts,
            toolConfig={"tools": self.TOOLS, "toolChoice": {"auto": {}}},
            inferenceConfig={"maxTokens": 4096, "temperature": 0.1}
        )

    async def query(
        self,
        text: str,
        history: list[dict] | None = None,
        context: str | None = None,
        session_id: str | None = None,
        use_orchestrator: bool | None = None,
    ) -> dict:
        """Query Nova with optional conversation history and RAG context.

        When the 8-agent orchestrator is available, it handles:
        - Intent classification
        - Dynamic tool selection
        - Quality enforcement
        - PII redaction

        Falls back to simple 3-tool mode if orchestrator is unavailable.

        Args:
            text: The user's query.
            history: Previous messages in Bedrock format.
            context: Retrieved RAG context to augment the query.
            session_id: Optional session ID for context tracking.
            use_orchestrator: Override orchestrator usage (None = use default).

        Returns:
            dict with success, response, and optional metadata.
        """
        if not self.available:
            return {
                "success": False,
                "error": "AI features not available (no AWS credentials). Running in LITE MODE - use /api/search or /api/autocomplete endpoints."
            }

        # Determine whether to use orchestrator
        should_use_orchestrator = (
            use_orchestrator if use_orchestrator is not None
            else (self._use_orchestrator and self._orchestrator is not None)
        )

        # Use 8-agent pipeline when available
        if should_use_orchestrator and self._orchestrator:
            return await self._query_orchestrated(text, session_id)

        # Fall back to simple mode
        return await self._query_simple(text, history, context)

    async def _query_orchestrated(
        self,
        text: str,
        session_id: str | None = None,
    ) -> dict:
        """Process query through 8-agent pipeline.

        Args:
            text: The user's query.
            session_id: Optional session ID.

        Returns:
            dict with response and metadata.
        """
        try:
            result = await self._orchestrator.process(
                query=text,
                session_id=session_id,
                trace_enabled=True,
            )

            return {
                "success": result.success,
                "response": result.response,
                "tool": ", ".join(result.tools_used) if result.tools_used else None,
                "route": result.route,
                "quality_score": result.quality_score,
                "latency_ms": result.latency_ms,
                "metadata": result.metadata,
            }

        except Exception as e:
            logger.error(f"Orchestrator query failed: {e}", exc_info=True)
            # Fall back to simple mode on error
            return await self._query_simple(text, None, None)

    async def _query_simple(
        self,
        text: str,
        history: list[dict] | None = None,
        context: str | None = None,
    ) -> dict:
        """Process query with simple 3-tool mode (original implementation).

        Args:
            text: The user's query.
            history: Previous messages in Bedrock format.
            context: Retrieved RAG context.

        Returns:
            dict with success, response, and optional tool used.
        """
        try:
            # Build messages: history + current query
            # Filter history to ensure only text content (no toolUse blocks that would require toolResult)
            messages = []
            if history:
                for msg in history:
                    # Only include messages with pure text content
                    clean_content = [b for b in msg.get("content", []) if "text" in b]
                    if clean_content:
                        messages.append({"role": msg["role"], "content": clean_content})
            messages.append({"role": "user", "content": [{"text": text}]})

            resp = self._converse(messages, context=context)
            content = resp["output"]["message"]["content"]

            # Handle ALL tool calls in the response
            tools = [b["toolUse"] for b in content if "toolUse" in b]
            if tools:
                # Execute all tools and collect results
                tool_results = []
                tool_names = []
                for tool in tools:
                    result = self._execute_tool(tool["name"], tool["input"])
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool["toolUseId"],
                            "content": [{"json": result}]
                        }
                    })
                    tool_names.append(tool["name"])

                # Continue with ALL tool results
                follow_messages = messages + [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": tool_results}
                ]
                follow = self._converse(follow_messages, context=context)

                if out := next((b["text"] for b in follow["output"]["message"]["content"] if "text" in b), None):
                    return {"success": True, "response": out, "tool": ", ".join(tool_names)}

            if out := next((b["text"] for b in content if "text" in b), None):
                return {"success": True, "response": out}
            return {"success": False, "error": "No response"}

        except ClientError as e:
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            if "Access" in error_msg or "credentials" in error_msg.lower():
                self.available = False
                return {"success": False, "error": "AWS access denied - check IAM permissions"}
            return {"success": False, "error": f"Nova: {error_msg}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_tool(self, name: str, params: dict) -> dict:
        """Execute a tool by name (simple mode only).

        Args:
            name: Tool name.
            params: Tool parameters.

        Returns:
            Tool execution result.
        """
        match name:
            case "lookup_crid":
                return self.db.lookup(params.get("crid", ""))
            case "search_customers":
                return self.db.search(
                    state=params.get("state"), city=params.get("city"),
                    min_moves=params.get("min_move_count"), limit=params.get("limit")
                )
            case "get_stats":
                return self.db.stats()
        return {"success": False, "error": f"Unknown tool: {name}"}

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics including orchestrator info.

        Returns:
            Dict with client and orchestrator stats.
        """
        stats = {
            "available": self.available,
            "model": self.model,
            "mode": "orchestrated" if (self._use_orchestrator and self._orchestrator) else "simple",
            "simple_tools": [t["toolSpec"]["name"] for t in self.TOOLS],
        }

        if self._orchestrator:
            stats["orchestrator"] = self._orchestrator.get_stats()

        return stats

    @property
    def orchestrator(self) -> QueryOrchestrator | None:
        """Get the underlying orchestrator if available."""
        return self._orchestrator
