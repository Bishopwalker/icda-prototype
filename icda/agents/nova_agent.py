"""Nova Agent - AI model orchestration with dynamic tools.

This agent:
1. Selects appropriate tools based on intent
2. Constructs prompts with context
3. Orchestrates Bedrock Nova calls
4. Handles tool execution loop
5. Returns AI-generated responses
"""

import logging
import os
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

# Configure boto3 client with extended timeout for long-running Bedrock calls
BOTO_CONFIG = Config(
    read_timeout=3600,  # 1 hour timeout
    connect_timeout=60,
    retries={'max_attempts': 3}
)

from .models import (
    IntentResult,
    QueryContext,
    SearchResult,
    KnowledgeContext,
    NovaResponse,
    TokenUsage,
    ParsedQuery,
)
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class NovaAgent:
    """Orchestrates AI model calls with dynamic tool selection.

    Follows the enforcer pattern - receives only the context it needs.
    """
    __slots__ = ("_client", "_model", "_tool_registry", "_available")

    # System prompt emphasizing factual accuracy to prevent hallucination
    SYSTEM_PROMPT = """You are ICDA, a customer data assistant. Be concise and accurate.

CRITICAL RULES:
1. ONLY use data from the provided CONTEXT - NEVER invent or hallucinate data
2. If no data matches the query, say "No matching data found" - do NOT make up results
3. If a state/location has no data, clearly inform the user instead of showing unrelated data
4. Never reveal SSN, financial, or health data
5. Maintain conversation context - reference prior exchanges when relevant

Interpret queries flexibly (e.g., "Nevada folks" = state NV)."""

    def __init__(
        self,
        region: str,
        model: str,
        tool_registry: ToolRegistry,
    ):
        """Initialize NovaAgent.

        Args:
            region: AWS region.
            model: Bedrock model ID.
            tool_registry: Dynamic tool registry.
        """
        self._model = model
        self._tool_registry = tool_registry
        self._client = None
        self._available = False

        # Check for AWS credentials
        if not os.environ.get("AWS_ACCESS_KEY_ID") and not os.environ.get("AWS_PROFILE"):
            logger.info("NovaAgent: No AWS credentials - AI features disabled")
            return

        try:
            self._client = boto3.client("bedrock-runtime", region_name=region, config=BOTO_CONFIG)
            self._available = True
            logger.info(f"NovaAgent: Connected ({model})")
        except NoCredentialsError:
            logger.warning("NovaAgent: AWS credentials not found")
        except Exception as e:
            logger.warning(f"NovaAgent: Init failed - {e}")

    @property
    def available(self) -> bool:
        """Check if agent is available."""
        return self._available

    async def generate(
        self,
        query: str,
        search_result: SearchResult,
        knowledge: KnowledgeContext,
        context: QueryContext,
        intent: IntentResult,
        model_override: str | None = None,
    ) -> NovaResponse:
        """Generate AI response with dynamic tools.

        Args:
            query: User query.
            search_result: Results from SearchAgent.
            knowledge: Context from KnowledgeAgent.
            context: Session context from ContextAgent.
            intent: Intent classification.
            model_override: Optional model ID to use instead of default.

        Returns:
            NovaResponse with generated text.
        """
        if not self._available:
            return self._fallback_response(query, search_result, knowledge)

        # ============================================================
        # CRITICAL: If state not available, skip AI and use fallback
        # The AI model tends to ignore context instructions, so we
        # handle this case directly with a structured response
        # ============================================================
        if getattr(search_result, 'state_not_available', False):
            return self._fallback_response(query, search_result, knowledge)

        # Use override model if provided
        model_to_use = model_override or self._model

        try:
            # CRITICAL FIX: Include conversation history for context continuity
            # This ensures the AI has complete conversation memory
            messages = self._build_messages(query, context)

            # Build minimal context from search (no knowledge)
            rag_context = self._build_context(search_result, knowledge)

            # Skip tools to reduce complexity and token usage
            tools = []

            # Call Nova - now returns token_usage
            response, tools_used, tool_results, token_usage = await self._converse(
                messages, tools, rag_context, model_to_use
            )

            return NovaResponse(
                response_text=response,
                tools_used=tools_used,
                tool_results=tool_results,
                model_used=model_to_use,
                token_usage=token_usage,
                ai_confidence=self._estimate_confidence(response, tools_used),
            )

        except ClientError as e:
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Nova error ({model_to_use}): {error_msg}")

            # Check for token limit errors
            if "token" in error_msg.lower() or "exceeded" in error_msg.lower():
                logger.warning("Token limit exceeded - using fallback response")
                return self._fallback_response(query, search_result, knowledge)

            if "Access" in error_msg or "credentials" in error_msg.lower():
                self._available = False
            return self._fallback_response(query, search_result, knowledge)

        except Exception as e:
            logger.error(f"NovaAgent error: {e}")
            return self._fallback_response(query, search_result, knowledge)

    # Maximum conversation history messages to include (pairs = N/2 turns)
    MAX_HISTORY_MESSAGES = 6  # 3 turns of conversation for better memory

    def _build_messages(
        self,
        query: str,
        context: QueryContext,
    ) -> list[dict[str, Any]]:
        """Build message list with conversation history for context continuity.

        Args:
            query: Current query.
            context: Session context.

        Returns:
            List of messages for converse API.
        """
        messages = []

        # Add relevant history (filter to text-only, limit to save tokens)
        # Include more history for better conversation memory
        if context.session_history:
            for msg in context.session_history[-self.MAX_HISTORY_MESSAGES:]:
                role = msg.get("role")
                content = msg.get("content", [])

                # Filter to text blocks only
                text_blocks = []
                if isinstance(content, list):
                    text_blocks = [b for b in content if isinstance(b, dict) and "text" in b]
                elif isinstance(content, str):
                    text_blocks = [{"text": content}]

                if text_blocks and role in ("user", "assistant"):
                    messages.append({"role": role, "content": text_blocks})

        # Add current query
        messages.append({"role": "user", "content": [{"text": query}]})

        return messages

    # Maximum results to include in context (reduces token usage)
    MAX_CONTEXT_RESULTS = 3

    def _build_context(
        self,
        search_result: SearchResult,
        knowledge: KnowledgeContext,
    ) -> str:
        """Build RAG context from search and knowledge.

        Args:
            search_result: Search results.
            knowledge: Knowledge context.

        Returns:
            Context string for the prompt (compact format to stay under token limit).
        """
        parts = []

        # Check if requested state is not available
        if getattr(search_result, 'state_not_available', False):
            requested_state = getattr(search_result, 'requested_state_name', None) or getattr(search_result, 'requested_state', 'requested state')
            available_states = getattr(search_result, 'available_states', [])
            state_counts = getattr(search_result, 'available_states_with_counts', {})
            
            parts.append(f"STATE NOT AVAILABLE: {requested_state}")
            parts.append(f"AVAILABLE STATES: {', '.join(available_states[:10])}")
            if state_counts:
                top_states = [(s, state_counts.get(s, 0)) for s in available_states[:5]]
                counts_str = ', '.join([f"{s}:{c}" for s, c in top_states])
                parts.append(f"TOP STATES (count): {counts_str}")
            parts.append("INSTRUCTION: Inform user this state has no data. Suggest available states.")
            return "\n".join(parts)

        # Add search results context - ultra-compact format to stay under token limits
        if search_result.results:
            total = search_result.total_matches
            shown = min(len(search_result.results), self.MAX_CONTEXT_RESULTS)
            parts.append(f"DATA ({shown}/{total}):")

            for i, customer in enumerate(search_result.results[:self.MAX_CONTEXT_RESULTS], 1):
                crid = customer.get("crid", "N/A")
                name = customer.get("name", "N/A")
                city = customer.get("city", "N/A")
                state = customer.get("state", "N/A")
                # Ultra-compact: CRID: Name - City, ST
                parts.append(f"{i}. {crid}: {name} - {city}, {state}")

            if total > self.MAX_CONTEXT_RESULTS:
                parts.append(f"...+{total - self.MAX_CONTEXT_RESULTS} more")
        else:
            parts.append("NO DATA FOUND")

        # Skip knowledge context to reduce tokens (search results are primary)
        return "\n".join(parts) if parts else ""

    async def _converse(
        self,
        messages: list[dict],
        tools: list[dict],
        context: str,
        model_id: str | None = None,
    ) -> tuple[str, list[str], list[dict], TokenUsage]:
        """Call Bedrock converse API.

        Args:
            messages: Conversation messages.
            tools: Tool definitions.
            context: RAG context.
            model_id: Optional model ID override.

        Returns:
            Tuple of (response_text, tools_used, tool_results, token_usage).
        """
        model_to_use = model_id or self._model

        # Build system prompt with context
        system_prompts = [{"text": self.SYSTEM_PROMPT}]
        if context:
            system_prompts.append({"text": f"\n\nCONTEXT:\n{context}"})

        # Initial call
        tool_config = {"tools": tools, "toolChoice": {"auto": {}}} if tools else None

        response = self._client.converse(
            modelId=model_to_use,
            messages=messages,
            system=system_prompts,
            toolConfig=tool_config,
            inferenceConfig={"maxTokens": 4096, "temperature": 0.1},
        )

        content = response["output"]["message"]["content"]
        tools_used = []
        tool_results_list = []

        # Extract token usage from initial response
        usage = response.get("usage", {})
        token_usage = TokenUsage(
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            total_tokens=usage.get("inputTokens", 0) + usage.get("outputTokens", 0),
        )

        # Handle tool calls
        tool_uses = [b["toolUse"] for b in content if "toolUse" in b]
        if tool_uses:
            # Execute tools
            tool_results = []
            for tool_use in tool_uses:
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]
                tools_used.append(tool_name)

                # Execute through registry
                result = self._tool_registry.execute(tool_name, tool_input)
                tool_results_list.append(result)

                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use["toolUseId"],
                        "content": [{"json": result}]
                    }
                })

            # Continue conversation with tool results
            follow_messages = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": tool_results}
            ]

            follow_response = self._client.converse(
                modelId=model_to_use,
                messages=follow_messages,
                system=system_prompts,
                toolConfig=tool_config,
                inferenceConfig={"maxTokens": 4096, "temperature": 0.1},
            )

            # Aggregate token usage from follow-up call
            follow_usage = follow_response.get("usage", {})
            token_usage = token_usage + TokenUsage(
                input_tokens=follow_usage.get("inputTokens", 0),
                output_tokens=follow_usage.get("outputTokens", 0),
                total_tokens=follow_usage.get("inputTokens", 0) + follow_usage.get("outputTokens", 0),
            )

            follow_content = follow_response["output"]["message"]["content"]
            text = next((b["text"] for b in follow_content if "text" in b), None)
            if text:
                return text, tools_used, tool_results_list, token_usage

        # Extract text response
        text = next((b["text"] for b in content if "text" in b), None)
        if text:
            return text, tools_used, tool_results_list, token_usage

        return "I couldn't generate a response.", tools_used, tool_results_list, token_usage

    def _fallback_response(
        self,
        query: str,
        search_result: SearchResult,
        knowledge: KnowledgeContext,
    ) -> NovaResponse:
        """Generate fallback response when Nova unavailable.

        Args:
            query: User query.
            search_result: Search results.
            knowledge: Knowledge context.

        Returns:
            NovaResponse with template-based text.
        """
        # Check if state was not available - give helpful redirect
        if getattr(search_result, 'state_not_available', False):
            requested_state = getattr(search_result, 'requested_state_name', None) or getattr(search_result, 'requested_state', 'that state')
            available_states = getattr(search_result, 'available_states', [])
            state_counts = getattr(search_result, 'available_states_with_counts', {})
            
            lines = [f"I don't have customer data for **{requested_state}** in this dataset.\n"]
            lines.append("**Available states with customer data:**\n")
            
            # Show top states with counts
            for state_code in available_states[:10]:
                count = state_counts.get(state_code, 0)
                lines.append(f"- **{state_code}**: {count:,} customers")
            
            if len(available_states) > 10:
                lines.append(f"- ... and {len(available_states) - 10} more states")
            
            lines.append("\nWould you like to search customers in one of these states instead?")
            
            return NovaResponse(
                response_text="\n".join(lines),
                tools_used=[],
                tool_results=[],
                model_used="fallback",
                token_usage=TokenUsage(),
                ai_confidence=0.9,  # High confidence - we know exactly what happened
            )
        
        # Generate response from search results with COMPLETE customer data
        if search_result.results:
            total = search_result.total_matches
            shown = min(len(search_result.results), 5)  # Limit to 5 for concise output

            # Format results with full customer details
            lines = [f"Found {total} customer(s). Here are the top {shown}:\n"]
            for i, customer in enumerate(search_result.results[:5], 1):
                crid = customer.get("crid", "N/A")
                name = customer.get("name", "N/A")
                address = customer.get("address", "N/A")
                city = customer.get("city", "N/A")
                state = customer.get("state", "N/A")
                zip_code = customer.get("zip", "N/A")
                moves = customer.get("move_count", 0)
                status = customer.get("status", "N/A")
                customer_type = customer.get("customer_type", "N/A")

                lines.append(f"{i}. **{name}** (CRID: {crid})")
                lines.append(f"   Address: {address}")
                lines.append(f"   Location: {city}, {state} {zip_code}")
                lines.append(f"   Moves: {moves} | Status: {status} | Type: {customer_type}")
                lines.append("")

            if total > 5:
                lines.append(f"... and {total - 5} more customers match your query.")

            return NovaResponse(
                response_text="\n".join(lines),
                tools_used=[],
                tool_results=[],
                model_used="fallback",
                token_usage=TokenUsage(),  # No tokens used for fallback
                ai_confidence=0.7,
            )

        return NovaResponse(
            response_text="No customers found matching your query. Try different search criteria or check the spelling.",
            tools_used=[],
            tool_results=[],
            model_used="fallback",
            token_usage=TokenUsage(),  # No tokens used for fallback
            ai_confidence=0.5,
        )

    def _estimate_confidence(
        self,
        response: str,
        tools_used: list[str],
    ) -> float:
        """Estimate response confidence.

        Args:
            response: Generated response.
            tools_used: Tools that were called.

        Returns:
            Confidence score (0.0 - 1.0).
        """
        confidence = 0.7  # Base confidence for AI response

        # Boost if tools were used (grounded response)
        if tools_used:
            confidence += 0.15

        # Reduce if response seems uncertain
        uncertain_phrases = ["i'm not sure", "i don't know", "i cannot", "unable to"]
        if any(phrase in response.lower() for phrase in uncertain_phrases):
            confidence -= 0.2

        return max(0.1, min(1.0, round(confidence, 3)))
