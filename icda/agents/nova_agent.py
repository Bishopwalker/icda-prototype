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
from botocore.exceptions import ClientError, NoCredentialsError

from .models import (
    IntentResult,
    QueryContext,
    SearchResult,
    KnowledgeContext,
    NovaResponse,
)
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class NovaAgent:
    """Orchestrates AI model calls with dynamic tool selection.

    Follows the enforcer pattern - receives only the context it needs.
    """
    __slots__ = ("_client", "_model", "_tool_registry", "_available")

    SYSTEM_PROMPT = """You are ICDA, an intelligent customer data assistant. Be concise, accurate, and helpful.

CAPABILITIES:
- Look up customers by CRID
- Search customers by state, city, or move count
- Provide statistics and aggregations
- Answer questions about customer data

GUIDELINES:
- Interpret queries flexibly (e.g., "Nevada folks" = state NV, "high movers" = min_move_count 3+)
- Use the provided context and search results
- Never reveal SSN, financial info, or health data
- Be direct and concise in responses
- Use conversation history for context in follow-up questions

When you have search results or data context, use that information to answer the query.
If you need to call a tool, select the most appropriate one based on the query."""

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
            self._client = boto3.client("bedrock-runtime", region_name=region)
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
    ) -> NovaResponse:
        """Generate AI response with dynamic tools.

        Args:
            query: User query.
            search_result: Results from SearchAgent.
            knowledge: Context from KnowledgeAgent.
            context: Session context from ContextAgent.
            intent: Intent classification.

        Returns:
            NovaResponse with generated text.
        """
        if not self._available:
            return self._fallback_response(query, search_result, knowledge)

        try:
            # Build messages with history
            messages = self._build_messages(query, context)

            # Build context from search and knowledge
            rag_context = self._build_context(search_result, knowledge)

            # Get tools for this intent
            tools = self._tool_registry.get_tools_for_intent(intent)

            # Call Nova
            response, tools_used, tool_results = await self._converse(
                messages, tools, rag_context
            )

            return NovaResponse(
                response_text=response,
                tools_used=tools_used,
                tool_results=tool_results,
                model_used=self._model,
                tokens_used=0,  # Would need to extract from response
                ai_confidence=self._estimate_confidence(response, tools_used),
            )

        except ClientError as e:
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Nova error: {error_msg}")
            if "Access" in error_msg or "credentials" in error_msg.lower():
                self._available = False
            return self._fallback_response(query, search_result, knowledge)

        except Exception as e:
            logger.error(f"NovaAgent error: {e}")
            return self._fallback_response(query, search_result, knowledge)

    def _build_messages(
        self,
        query: str,
        context: QueryContext,
    ) -> list[dict[str, Any]]:
        """Build message list with history.

        Args:
            query: Current query.
            context: Session context.

        Returns:
            List of messages for converse API.
        """
        messages = []

        # Add relevant history (filter to text-only)
        if context.session_history:
            for msg in context.session_history[-6:]:  # Last 6 messages
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
            Context string for the prompt.
        """
        parts = []

        # Add search results context
        if search_result.results:
            parts.append("CUSTOMER DATA:")
            for i, customer in enumerate(search_result.results[:5], 1):
                crid = customer.get("crid", "N/A")
                name = customer.get("name", "N/A")
                city = customer.get("city", "N/A")
                state = customer.get("state", "N/A")
                moves = customer.get("move_count", 0)
                parts.append(f"  {i}. {crid}: {name} - {city}, {state} ({moves} moves)")

            if search_result.total_matches > 5:
                parts.append(f"  ... and {search_result.total_matches - 5} more")

        # Add knowledge context
        if knowledge.relevant_chunks:
            parts.append("\nRELEVANT DOCUMENTATION:")
            for chunk in knowledge.relevant_chunks[:3]:
                text = chunk.get("text", "")[:200]
                source = chunk.get("source", "")
                parts.append(f"  - {text}... (from {source})")

        return "\n".join(parts) if parts else ""

    async def _converse(
        self,
        messages: list[dict],
        tools: list[dict],
        context: str,
    ) -> tuple[str, list[str], list[dict]]:
        """Call Bedrock converse API.

        Args:
            messages: Conversation messages.
            tools: Tool definitions.
            context: RAG context.

        Returns:
            Tuple of (response_text, tools_used, tool_results).
        """
        # Build system prompt with context
        system_prompts = [{"text": self.SYSTEM_PROMPT}]
        if context:
            system_prompts.append({"text": f"\n\nCONTEXT:\n{context}"})

        # Initial call
        tool_config = {"tools": tools, "toolChoice": {"auto": {}}} if tools else None

        response = self._client.converse(
            modelId=self._model,
            messages=messages,
            system=system_prompts,
            toolConfig=tool_config,
            inferenceConfig={"maxTokens": 4096, "temperature": 0.1},
        )

        content = response["output"]["message"]["content"]
        tools_used = []
        tool_results_list = []

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
                modelId=self._model,
                messages=follow_messages,
                system=system_prompts,
                toolConfig=tool_config,
                inferenceConfig={"maxTokens": 4096, "temperature": 0.1},
            )

            follow_content = follow_response["output"]["message"]["content"]
            text = next((b["text"] for b in follow_content if "text" in b), None)
            if text:
                return text, tools_used, tool_results_list

        # Extract text response
        text = next((b["text"] for b in content if "text" in b), None)
        if text:
            return text, tools_used, tool_results_list

        return "I couldn't generate a response.", tools_used, tool_results_list

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
        # Generate response from search results
        if search_result.results:
            count = len(search_result.results)
            total = search_result.total_matches

            # Format results
            lines = [f"Found {total} customer(s):"]
            for customer in search_result.results[:5]:
                crid = customer.get("crid", "N/A")
                name = customer.get("name", "N/A")
                city = customer.get("city", "N/A")
                state = customer.get("state", "N/A")
                lines.append(f"  - {crid}: {name} ({city}, {state})")

            if total > 5:
                lines.append(f"  ... and {total - 5} more")

            return NovaResponse(
                response_text="\n".join(lines),
                tools_used=[],
                tool_results=[],
                model_used="fallback",
                tokens_used=0,
                ai_confidence=0.5,
            )

        return NovaResponse(
            response_text="AI features are not available. Please use direct search or autocomplete endpoints.",
            tools_used=[],
            tool_results=[],
            model_used="fallback",
            tokens_used=0,
            ai_confidence=0.1,
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
