"""Nova Client - Amazon Bedrock Nova integration for ICDA.

This module provides AI-powered query processing using AWS Bedrock Nova.
Supports two modes:
1. Simple mode: Direct tool calling with 3 static tools
2. Orchestrated mode: 8-agent pipeline with dynamic tools

The Bedrock Converse API flow:
1. Send user message with tool definitions
2. Model may respond with text OR tool_use requests
3. Execute tools and send results back
4. Model generates final response

Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
"""

import logging
import os
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from .database import CustomerDB
from .agents import QueryOrchestrator, create_query_orchestrator

logger = logging.getLogger(__name__)

# Boto3 client config with extended timeout for Bedrock
BOTO_CONFIG = Config(
    read_timeout=300,
    connect_timeout=60,
    retries={"max_attempts": 3},
)

# Maximum tool call iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 5


class NovaClient:
    """
    Amazon Bedrock Nova client for AI-powered queries.
    Gracefully handles missing AWS credentials.

    Supports two modes:
    1. Simple mode: Direct tool calling with 3 static tools
    2. Orchestrated mode: 8-agent pipeline with dynamic tools

    The orchestrated mode is enabled by default when available.
    """
    __slots__ = ("client", "model", "available", "db", "_orchestrator", "_use_orchestrator", "_download_manager")

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
        {"toolSpec": {"name": "search_customers", "description": "Search and COUNT customers with filters. USE THIS for any filtered queries like 'customers in California', 'apartment renters', 'how many residential customers', etc. Returns matching customers with total count.",
            "inputSchema": {"json": {"type": "object", "properties": {
                "state": {"type": "string", "description": "Two-letter state code (NV, CA, TX, NY, FL, etc). Convert state names: California=CA, Nevada=NV, Texas=TX."},
                "city": {"type": "string", "description": "City name to filter by"},
                "min_move_count": {"type": "integer", "description": "Minimum number of moves. Use 2-3 for 'frequent movers', 5+ for 'high movers'"},
                "customer_type": {"type": "string", "description": "Customer type: RESIDENTIAL (renters, homeowners), BUSINESS (companies), or PO_BOX. Use RESIDENTIAL for 'renters' or 'apartment' queries."},
                "has_apartment": {"type": "boolean", "description": "Set true to filter for apartment/unit addresses only (addresses containing Apt or Unit). Use for 'apartment renters' queries."},
                "limit": {"type": "integer", "description": "Max results to return (default 10, max 100)"}}}}}},
        {"toolSpec": {"name": "get_stats", "description": "Get ONLY overall statistics by state (no filters). Use ONLY for general breakdowns like 'show stats' or 'breakdown by state'. Do NOT use for filtered counts - use search_customers instead.",
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
        llm_enforcer=None,
        use_orchestrator: bool = True,
        download_manager=None,
        model_config: dict[str, Any] | None = None,
    ):
        """Initialize NovaClient with optional 7-agent pipeline + LLM enforcer.

        Args:
            region: AWS region for Bedrock.
            model: Bedrock model ID (base/micro model).
            db: CustomerDB instance.
            vector_index: Optional VectorIndex for semantic search.
            knowledge: Optional KnowledgeManager for RAG.
            address_orchestrator: Optional address verification orchestrator.
            session_store: Optional session store for context.
            guardrails: Optional Guardrails for PII filtering.
            llm_enforcer: Optional LLMEnforcer for AI-powered validation.
            use_orchestrator: Whether to use 8-agent pipeline (default True).
            download_manager: Optional DownloadTokenManager for pagination.
            model_config: Optional model routing config with keys:
                - nova_lite_model: Model ID for medium complexity
                - nova_pro_model: Model ID for complex queries
                - model_routing_threshold: Confidence threshold for escalation
        """
        self.model = model
        self.db = db
        self.client = None
        self.available = False
        self._orchestrator = None
        self._use_orchestrator = use_orchestrator
        self._download_manager = download_manager

        # Check if AWS credentials are available (supports default credential chain)
        try:
            session = boto3.Session()
            if session.get_credentials() is None:
                logger.info("Nova: No AWS credentials - AI features disabled (LITE MODE)")
                return
        except Exception:
            logger.info("Nova: No AWS credentials - AI features disabled (LITE MODE)")
            return

        try:
            self.client = boto3.client("bedrock-runtime", region_name=region, config=BOTO_CONFIG)
            self.available = True
            logger.info(f"Nova: Connected ({model})")

            # Initialize 7-agent orchestrator + LLM enforcer if enabled
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
                        llm_enforcer=llm_enforcer,
                        download_manager=download_manager,
                        config=model_config,  # Pass model routing config
                    )
                    enforcer_status = f"with {llm_enforcer.client.provider}" if (llm_enforcer and llm_enforcer.available) else "without enforcer"
                    logger.info(f"Nova: 7-agent orchestrator enabled ({enforcer_status})")
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
            dict with response and enhanced metadata (token_usage, trace, pagination).
        """
        try:
            result = await self._orchestrator.process(
                query=text,
                session_id=session_id,
                trace_enabled=True,
            )

            response_dict = {
                "success": result.success,
                "response": result.response,
                "tool": ", ".join(result.tools_used) if result.tools_used else None,
                "route": result.route,
                "quality_score": result.quality_score,
                "latency_ms": result.latency_ms,
                "metadata": result.metadata,
            }

            # Add enhanced pipeline data
            if result.token_usage:
                response_dict["token_usage"] = result.token_usage
            if result.trace:
                response_dict["trace"] = result.trace
            if result.pagination:
                response_dict["pagination"] = result.pagination
            if result.model_used:
                response_dict["model_used"] = result.model_used
            if result.results:
                response_dict["results"] = result.results

            return response_dict

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
        """Process query using simple 3-tool mode with agentic loop.

        This implements the Bedrock Converse API pattern:
        1. Build conversation messages from history + current query
        2. Call model with tool definitions
        3. If model requests tools, execute them and continue
        4. Repeat until model returns text response (agentic loop)

        Args:
            text: The user's query.
            history: Previous conversation messages.
            context: Optional RAG context to augment the query.

        Returns:
            dict with keys: success, response, tool, latency_ms, iterations
        """
        start_time = time.time()
        tools_used = []

        try:
            # Step 1: Build conversation messages
            messages = self._build_messages(history, text)

            # Step 2: Agentic loop - keep calling model until we get a text response
            for iteration in range(MAX_TOOL_ITERATIONS):
                logger.debug(f"Simple mode iteration {iteration + 1}")

                # Call Bedrock Converse API
                response = self._converse(messages, context=context)
                assistant_message = response["output"]["message"]
                content_blocks = assistant_message["content"]

                # Check stop reason to understand model's intent
                stop_reason = response.get("stopReason", "end_turn")

                # Step 3: Extract tool requests from response
                tool_requests = self._extract_tool_requests(content_blocks)

                # If no tools requested, extract text and return
                if not tool_requests:
                    final_text = self._extract_text(content_blocks)
                    if final_text:
                        return self._build_success_response(
                            response=final_text,
                            tools_used=tools_used,
                            start_time=start_time,
                            iterations=iteration + 1,
                        )
                    return {"success": False, "error": "Model returned no text response"}

                # Step 4: Execute all requested tools
                tool_results = self._execute_tools(tool_requests)
                tools_used.extend([t["name"] for t in tool_requests])

                # Step 5: Add assistant response and tool results to conversation
                messages.append({"role": "assistant", "content": content_blocks})
                messages.append({"role": "user", "content": tool_results})

                # If stop reason is "end_turn", model may want to respond after tools
                # Continue loop to get the final response

            # Exceeded max iterations
            logger.warning(f"Exceeded {MAX_TOOL_ITERATIONS} tool iterations")
            return {
                "success": False,
                "error": f"Query required more than {MAX_TOOL_ITERATIONS} tool calls",
                "tools_used": tools_used,
            }

        except ClientError as e:
            return self._handle_client_error(e)
        except Exception as e:
            logger.error(f"Simple query failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Helper Methods - Message Building
    # =========================================================================

    def _build_messages(
        self,
        history: list[dict] | None,
        current_query: str,
    ) -> list[dict]:
        """Build conversation messages for Bedrock Converse API.

        Filters history to only include text content (removes any toolUse
        blocks that would require matching toolResult blocks).

        Args:
            history: Previous conversation messages.
            current_query: The current user query.

        Returns:
            List of message dicts in Bedrock format.
        """
        messages = []

        # Add filtered history
        if history:
            for msg in history:
                role = msg.get("role")
                content = msg.get("content", [])

                # Only include text blocks (filter out tool blocks)
                text_blocks = [
                    block for block in content
                    if isinstance(block, dict) and "text" in block
                ]

                if text_blocks and role in ("user", "assistant"):
                    messages.append({"role": role, "content": text_blocks})

        # Add current query
        messages.append({
            "role": "user",
            "content": [{"text": current_query}]
        })

        return messages

    # =========================================================================
    # Helper Methods - Response Parsing
    # =========================================================================

    def _extract_tool_requests(self, content_blocks: list[dict]) -> list[dict]:
        """Extract tool use requests from model response.

        Args:
            content_blocks: Content blocks from model response.

        Returns:
            List of tool request dicts with keys: toolUseId, name, input
        """
        return [
            block["toolUse"]
            for block in content_blocks
            if "toolUse" in block
        ]

    def _extract_text(self, content_blocks: list[dict]) -> str | None:
        """Extract text response from model output.

        Args:
            content_blocks: Content blocks from model response.

        Returns:
            Text string or None if no text found.
        """
        for block in content_blocks:
            if "text" in block:
                return block["text"]
        return None

    # =========================================================================
    # Helper Methods - Tool Execution
    # =========================================================================

    def _execute_tools(self, tool_requests: list[dict]) -> list[dict]:
        """Execute multiple tool requests and format results.

        Args:
            tool_requests: List of tool request dicts from model.

        Returns:
            List of toolResult blocks for Bedrock API.
        """
        results = []

        for request in tool_requests:
            tool_name = request["name"]
            tool_input = request["input"]
            tool_id = request["toolUseId"]

            logger.debug(f"Executing tool: {tool_name} with input: {tool_input}")

            # Execute the tool
            result = self._execute_tool(tool_name, tool_input)

            # Format as Bedrock toolResult
            results.append({
                "toolResult": {
                    "toolUseId": tool_id,
                    "content": [{"json": result}]
                }
            })

        return results

    # =========================================================================
    # Helper Methods - Response Building
    # =========================================================================

    def _build_success_response(
        self,
        response: str,
        tools_used: list[str],
        start_time: float,
        iterations: int,
    ) -> dict:
        """Build successful response dict with metrics.

        Args:
            response: The text response from model.
            tools_used: List of tool names that were called.
            start_time: Query start time for latency calculation.
            iterations: Number of agentic loop iterations.

        Returns:
            Response dict with success=True and metadata.
        """
        latency_ms = int((time.time() - start_time) * 1000)

        result = {
            "success": True,
            "response": response,
            "latency_ms": latency_ms,
            "iterations": iterations,
        }

        if tools_used:
            result["tool"] = ", ".join(tools_used)

        return result

    def _handle_client_error(self, error: ClientError) -> dict:
        """Handle AWS ClientError with appropriate response.

        Args:
            error: The ClientError from boto3.

        Returns:
            Error response dict.
        """
        error_msg = error.response.get("Error", {}).get("Message", str(error))

        # Check for auth errors
        if "Access" in error_msg or "credentials" in error_msg.lower():
            self.available = False
            logger.error("AWS access denied - disabling Nova")
            return {"success": False, "error": "AWS access denied - check IAM permissions"}

        # Check for throttling
        if "throttl" in error_msg.lower():
            logger.warning(f"Nova throttled: {error_msg}")
            return {"success": False, "error": "Request throttled - please retry"}

        logger.error(f"Nova client error: {error_msg}")
        return {"success": False, "error": f"Nova: {error_msg}"}

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
