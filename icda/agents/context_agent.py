"""Context Agent - Extracts session and conversation context.

This agent extracts relevant context from:
1. Session history (previous messages)
2. Referenced entities (CRIDs, names from prior conversation)
3. Geographic context (state, city, zip from history)
4. User preferences inferred from behavior
5. Prior query results for follow-up detection
"""

import logging
import re
from typing import Any

from .models import IntentResult, QueryContext

logger = logging.getLogger(__name__)


class ContextAgent:
    """Extracts context from session history and conversation.

    Follows the enforcer pattern - receives only the context it needs.
    """
    __slots__ = ("_session_manager", "_available")

    # State codes for extraction
    VALID_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "PR", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
    }

    # State name to code mapping
    STATE_NAMES = {
        "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
        "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
        "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
        "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
        "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
        "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
        "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
        "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
        "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
        "oregon": "OR", "pennsylvania": "PA", "puerto rico": "PR", "rhode island": "RI",
        "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
        "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
        "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
        "district of columbia": "DC", "d.c.": "DC", "dc": "DC",
    }

    # Follow-up indicators
    FOLLOW_UP_PATTERNS = (
        r"\bthose\b",
        r"\bthem\b",
        r"\bthey\b",
        r"\bit\b",
        r"\bthe same\b",
        r"\bsame\s+customers?\b",
        r"\bmore\s+about\b",
        r"\bmore\s+details?\b",
        r"\bwhat\s+about\b",
        r"\bhow\s+about\b",
        r"\band\s+also\b",
        r"\bcan\s+you\s+also\b",
        r"\btell\s+me\s+more\b",
        r"\bshow\s+me\s+more\b",
    )

    def __init__(self, session_manager=None):
        """Initialize ContextAgent.

        Args:
            session_manager: Optional SessionManager for retrieving history.
        """
        self._session_manager = session_manager
        self._available = True

    @property
    def available(self) -> bool:
        """Check if agent is available."""
        return self._available

    async def extract(
        self,
        session_id: str | None,
        query: str,
        intent: IntentResult,
    ) -> QueryContext:
        """Extract context from session and query.

        Args:
            session_id: Session identifier.
            query: Current user query.
            intent: Classification result from IntentAgent.

        Returns:
            QueryContext with extracted information.
        """
        # Get session history
        history = await self._get_session_history(session_id)

        # Extract entities from history
        referenced_entities = self._extract_entities(history)

        # Extract geographic context
        geographic_context = self._extract_geographic(history, query)

        # Infer user preferences
        user_preferences = self._infer_preferences(history)

        # Get prior results if available
        prior_results = self._get_prior_results(history)

        # Detect if this is a follow-up question
        is_follow_up = self._detect_follow_up(query, history)

        # Calculate context confidence
        context_confidence = self._calculate_confidence(
            history, geographic_context, is_follow_up
        )

        return QueryContext(
            session_history=history,
            referenced_entities=referenced_entities,
            geographic_context=geographic_context,
            user_preferences=user_preferences,
            prior_results=prior_results,
            is_follow_up=is_follow_up,
            context_confidence=context_confidence,
        )

    async def _get_session_history(self, session_id: str | None) -> list[dict[str, Any]]:
        """Retrieve session history.

        Args:
            session_id: Session identifier.

        Returns:
            List of previous messages.
        """
        if not session_id or not self._session_manager:
            return []

        try:
            session = await self._session_manager.get(session_id)
            if session and session.messages:
                # Return last 10 messages in Bedrock format for context
                return session.get_history(max_messages=10)
            return []
        except Exception as e:
            logger.warning(f"Failed to get session history: {e}")
            return []

    def _extract_entities(self, history: list[dict[str, Any]]) -> list[str]:
        """Extract referenced entities from history.

        Args:
            history: Conversation history.

        Returns:
            List of entity identifiers (CRIDs, names).
        """
        entities = []

        for msg in history:
            text = self._get_message_text(msg)

            # Extract CRIDs
            crids = re.findall(r"CRID[-\s]?\d+", text, re.IGNORECASE)
            entities.extend(crid.upper().replace(" ", "-") for crid in crids)

            # Extract customer names (from assistant responses mentioning customers)
            if msg.get("role") == "assistant":
                # Look for name patterns like "John Smith" or "customer John"
                names = re.findall(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b", text)
                entities.extend(names[:5])  # Limit names

        # Remove duplicates while preserving order
        return list(dict.fromkeys(entities))[:20]

    def _extract_geographic(
        self,
        history: list[dict[str, Any]],
        current_query: str,
    ) -> dict[str, str | None]:
        """Extract geographic context from history and current query.

        Args:
            history: Conversation history.
            current_query: Current user query.

        Returns:
            Dict with state, city, zip extracted.
        """
        context = {
            "state": None,
            "city": None,
            "zip_code": None,
        }

        # Search current query first (highest priority)
        all_text = [current_query] + [self._get_message_text(m) for m in reversed(history)]

        for text in all_text:
            text_lower = text.lower()

            # Extract state (stop at first found)
            if not context["state"]:
                # Check state codes
                state_match = re.search(r"\b([A-Z]{2})\b", text)
                if state_match and state_match.group(1) in self.VALID_STATES:
                    context["state"] = state_match.group(1)
                else:
                    # Check state names
                    for name, code in self.STATE_NAMES.items():
                        if name in text_lower:
                            context["state"] = code
                            break

            # Extract ZIP code
            if not context["zip_code"]:
                zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", text)
                if zip_match:
                    context["zip_code"] = zip_match.group(1)

            # Extract city (basic heuristic - capitalize words before state)
            if not context["city"] and context["state"]:
                # Look for "City, ST" or "City ST" pattern
                city_pattern = rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,?\s*{context['state']}"
                city_match = re.search(city_pattern, text)
                if city_match:
                    context["city"] = city_match.group(1)

        return context

    def _infer_preferences(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        """Infer user preferences from history.

        Args:
            history: Conversation history.

        Returns:
            Dict of inferred preferences.
        """
        preferences = {
            "preferred_limit": 10,
            "prefers_details": False,
            "prefers_summary": False,
        }

        for msg in history:
            if msg.get("role") != "user":
                continue

            text = self._get_message_text(msg).lower()

            # Check for limit preferences
            limit_match = re.search(r"\b(\d+)\s+(?:results?|customers?|records?)\b", text)
            if limit_match:
                preferences["preferred_limit"] = min(int(limit_match.group(1)), 100)

            # Check for detail preference
            if any(word in text for word in ["detail", "full", "complete", "all info"]):
                preferences["prefers_details"] = True

            # Check for summary preference
            if any(word in text for word in ["summary", "brief", "quick", "overview"]):
                preferences["prefers_summary"] = True

        return preferences

    def _get_prior_results(self, history: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """Get results from the most recent query.

        Args:
            history: Conversation history.

        Returns:
            Prior query results if available.
        """
        # Look for assistant messages with customer data
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                # Check if message contains tool results
                content = msg.get("content", [])
                for block in content:
                    if "toolResult" in block:
                        result = block["toolResult"].get("content", [])
                        for item in result:
                            if "json" in item:
                                return item["json"].get("results", [])
        return None

    def _detect_follow_up(self, query: str, history: list[dict[str, Any]]) -> bool:
        """Detect if the current query is a follow-up.

        Args:
            query: Current query.
            history: Conversation history.

        Returns:
            True if this appears to be a follow-up question.
        """
        if not history:
            return False

        query_lower = query.lower()

        # Check for follow-up patterns
        for pattern in self.FOLLOW_UP_PATTERNS:
            if re.search(pattern, query_lower):
                return True

        # Check if query is very short (likely a follow-up)
        if len(query.split()) <= 3 and history:
            return True

        return False

    def _calculate_confidence(
        self,
        history: list[dict[str, Any]],
        geographic: dict[str, str | None],
        is_follow_up: bool,
    ) -> float:
        """Calculate confidence in extracted context.

        Args:
            history: Conversation history.
            geographic: Extracted geographic context.
            is_follow_up: Whether this is a follow-up.

        Returns:
            Confidence score (0.0 - 1.0).
        """
        confidence = 0.5  # Base confidence

        # Boost for having history
        if history:
            confidence += 0.1 * min(len(history), 5) / 5

        # Boost for geographic context
        geo_count = sum(1 for v in geographic.values() if v)
        confidence += 0.1 * geo_count / 3

        # Follow-up with history is high confidence
        if is_follow_up and history:
            confidence += 0.2

        # Reduce if follow-up but no history
        if is_follow_up and not history:
            confidence -= 0.3

        return max(0.0, min(1.0, round(confidence, 3)))

    def _get_message_text(self, msg: dict[str, Any]) -> str:
        """Extract text content from a message.

        Args:
            msg: Message dict.

        Returns:
            Combined text content.
        """
        content = msg.get("content", [])
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    texts.append(block["text"])
            return " ".join(texts)
        return ""
