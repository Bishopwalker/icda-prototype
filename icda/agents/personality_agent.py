"""Personality Agent - Adds warmth, wit, and character to responses.

Implements a "Witty Expert" personality that is:
- Knowledgeable and confident
- Clever with occasional wit
- Empathetic when results are empty
- Professional but never robotic
"""

import logging
import random
import re
from typing import Any

from .models import (
    PersonalityConfig,
    PersonalityContext,
    PersonalityStyle,
    IntentResult,
    MemoryContext,
    SearchResult,
)

logger = logging.getLogger(__name__)


# Witty openers for different scenarios
WITTY_OPENERS = {
    "found_results": [
        "Ah, here we go!",
        "Found what you're looking for.",
        "Got 'em!",
        "Right, let's see...",
        "Here's what I found.",
    ],
    "exact_match": [
        "Nailed it!",
        "Bingo!",
        "Found exactly what you're after.",
        "That's a match.",
        "Right on target.",
    ],
    "many_results": [
        "Plenty to choose from!",
        "No shortage here.",
        "You've got options.",
        "Quite the selection.",
        "A healthy batch.",
    ],
    "few_results": [
        "Found a couple.",
        "A select few.",
        "Not many, but here they are.",
        "Quality over quantity.",
    ],
    "state_specific": {
        "CA": "California dreamin'? Here's what I found.",
        "TX": "Everything's bigger in Texas - including our customer list.",
        "NY": "The Big Apple delivers.",
        "FL": "Sunshine State coming through.",
        "NV": "What happens in Nevada... shows up in our database.",
        "AZ": "Desert heat, cool data.",
        "CO": "Rocky Mountain high on results.",
        "WA": "Pacific Northwest, reporting in.",
        "OR": "Oregon Trail? More like Oregon customers.",
        "default": "Here's what I found in {state}.",
    },
}

# Empathetic responses for empty results
EMPTY_RESULT_RESPONSES = [
    "Hmm, no luck with that one.",
    "Coming up empty here.",
    "No matches on that search.",
    "That's a ghost town in our database.",
    "Nobody home with those criteria.",
]

# Witty no-state-data responses
NO_STATE_DATA_RESPONSES = [
    "Turns out that state is a bit of a mystery in our dataset.",
    "That state hasn't checked in with us yet.",
    "Our coverage doesn't extend there, unfortunately.",
    "That's uncharted territory for our data.",
]

# Suggestions for empty results
EMPTY_SUGGESTIONS = [
    "Want to try a different state?",
    "Maybe broaden the search a bit?",
    "Try removing some filters?",
    "Different spelling perhaps?",
]

# Follow-up conversation starters
FOLLOW_UP_STARTERS = [
    "Anything else I can dig up?",
    "Need more details on any of these?",
    "Want to narrow it down further?",
    "Shall I look for something specific?",
]


class PersonalityAgent:
    """Agent for adding personality to responses.

    Transforms clinical responses into engaging, witty ones
    while maintaining professionalism and accuracy.
    """

    __slots__ = ("_config", "_style")

    def __init__(self, config: PersonalityConfig | None = None):
        """Initialize PersonalityAgent.

        Args:
            config: Personality configuration.
        """
        self._config = config or PersonalityConfig()
        self._style = self._config.style

    @property
    def available(self) -> bool:
        """Always available."""
        return True

    async def enhance(
        self,
        response: str,
        query: str,
        intent: IntentResult,
        search_result: SearchResult | None = None,
        memory: MemoryContext | None = None,
    ) -> PersonalityContext:
        """Enhance response with personality.

        Args:
            response: Original response text.
            query: Original query.
            intent: Intent classification.
            search_result: Search results for context.
            memory: Memory context for continuity.

        Returns:
            PersonalityContext with enhanced response.
        """
        if not self._config.warmth_level > 0:
            return PersonalityContext(
                enhanced_response=response,
                original_response=response,
                personality_applied=False,
                tone_score=0.0,
            )

        enhancements = []
        enhanced = response

        # Determine response type and apply appropriate enhancement
        is_empty = self._is_empty_result(response, search_result)
        is_state_unavailable = self._is_state_unavailable(search_result)

        if is_state_unavailable:
            enhanced = self._enhance_state_unavailable(
                enhanced, search_result, enhancements
            )
        elif is_empty:
            enhanced = self._enhance_empty_result(enhanced, query, enhancements)
        else:
            enhanced = self._enhance_success_result(
                enhanced, query, search_result, memory, enhancements
            )

        # Add conversational continuity for follow-ups
        if memory and memory.active_customer:
            enhanced = self._add_memory_reference(
                enhanced, memory, enhancements
            )

        # Calculate tone score
        tone_score = self._calculate_tone_score(enhanced, enhancements)

        return PersonalityContext(
            enhanced_response=enhanced,
            original_response=response,
            personality_applied=len(enhancements) > 0,
            enhancements_made=enhancements,
            tone_score=tone_score,
        )

    def _is_empty_result(
        self,
        response: str,
        search_result: SearchResult | None,
    ) -> bool:
        """Check if this is an empty result response."""
        if search_result and search_result.total_matches == 0:
            return True

        empty_phrases = [
            "no customers found",
            "no results",
            "no matches",
            "couldn't find",
            "no data found",
        ]
        response_lower = response.lower()
        return any(phrase in response_lower for phrase in empty_phrases)

    def _is_state_unavailable(
        self,
        search_result: SearchResult | None,
    ) -> bool:
        """Check if state data is unavailable."""
        return search_result and search_result.state_not_available

    def _enhance_state_unavailable(
        self,
        response: str,
        search_result: SearchResult,
        enhancements: list[str],
    ) -> str:
        """Enhance response when state data is unavailable."""
        state_name = search_result.requested_state_name or search_result.requested_state

        if self._config.humor_enabled:
            opener = random.choice(NO_STATE_DATA_RESPONSES)
            enhancements.append("added_witty_unavailable")
        else:
            opener = "That state isn't in our dataset."
            enhancements.append("added_unavailable_note")

        # Build alternative suggestion
        available = search_result.available_states[:5]
        if available:
            alt_text = f"But hey, we've got data for {', '.join(available)} and more."
        else:
            alt_text = ""

        # Reconstruct response
        enhanced = f"{opener} {state_name} {alt_text}\n\n{response}"

        return enhanced.strip()

    def _enhance_empty_result(
        self,
        response: str,
        query: str,
        enhancements: list[str],
    ) -> str:
        """Enhance empty result response with empathy."""
        if not self._config.empathy_enabled:
            return response

        if self._config.humor_enabled:
            opener = random.choice(EMPTY_RESULT_RESPONSES)
            suggestion = random.choice(EMPTY_SUGGESTIONS)
            enhancements.append("added_witty_empathy")
        else:
            opener = "No matches found."
            suggestion = "Try adjusting your search criteria."
            enhancements.append("added_empathy")

        # Replace or prepend
        if response.lower().startswith("no"):
            enhanced = f"{opener} {suggestion}"
        else:
            enhanced = f"{opener}\n\n{response}\n\n{suggestion}"

        return enhanced

    def _enhance_success_result(
        self,
        response: str,
        query: str,
        search_result: SearchResult | None,
        memory: MemoryContext | None,
        enhancements: list[str],
    ) -> str:
        """Enhance successful result response."""
        # Determine the right opener
        opener = self._get_success_opener(query, search_result, enhancements)

        # Check if response already has a good opener
        if self._has_opener(response):
            return response

        # Add opener
        enhanced = f"{opener}\n\n{response}"
        return enhanced

    def _get_success_opener(
        self,
        query: str,
        search_result: SearchResult | None,
        enhancements: list[str],
    ) -> str:
        """Get appropriate opener for success response."""
        if not self._config.humor_enabled:
            return "Here's what I found:"

        total = search_result.total_matches if search_result else 0
        state = self._extract_state_from_query(query)

        # State-specific opener
        if state and state in WITTY_OPENERS["state_specific"]:
            enhancements.append("added_state_wit")
            return WITTY_OPENERS["state_specific"][state]
        elif state:
            enhancements.append("added_state_opener")
            return WITTY_OPENERS["state_specific"]["default"].format(state=state)

        # Count-based opener
        if total == 1:
            enhancements.append("added_exact_match")
            return random.choice(WITTY_OPENERS["exact_match"])
        elif total > 50:
            enhancements.append("added_many_results")
            return random.choice(WITTY_OPENERS["many_results"])
        elif total > 0 and total <= 5:
            enhancements.append("added_few_results")
            return random.choice(WITTY_OPENERS["few_results"])
        else:
            enhancements.append("added_found_opener")
            return random.choice(WITTY_OPENERS["found_results"])

    def _has_opener(self, response: str) -> bool:
        """Check if response already has an opener."""
        opener_patterns = [
            r"^(here's|found|got|i found)",
            r"^(there are|we have|i have)",
            r"^(ah|great|excellent|bingo)",
        ]
        response_lower = response.lower().strip()
        return any(
            re.match(pattern, response_lower)
            for pattern in opener_patterns
        )

    def _extract_state_from_query(self, query: str) -> str | None:
        """Extract state code from query."""
        # Look for state codes
        state_pattern = r"\b([A-Z]{2})\b"
        matches = re.findall(state_pattern, query.upper())
        if matches:
            return matches[0]
        return None

    def _add_memory_reference(
        self,
        response: str,
        memory: MemoryContext,
        enhancements: list[str],
    ) -> str:
        """Add reference to previous conversation."""
        if not memory.active_customer:
            return response

        # Check if we're continuing a conversation
        if memory.recall_confidence > 0.5:
            customer_name = memory.active_customer.canonical_name
            if customer_name.lower() not in response.lower():
                # Add subtle continuity reference
                enhancements.append("added_memory_reference")
                # Don't modify response, let it stand - continuity is implicit

        return response

    def _calculate_tone_score(
        self,
        response: str,
        enhancements: list[str],
    ) -> float:
        """Calculate warmth/tone score of response."""
        score = 0.3  # Base score

        # Boost for enhancements
        if enhancements:
            score += 0.1 * min(len(enhancements), 3)

        # Check for warm language
        warm_words = ["here's", "found", "got", "great", "excellent"]
        response_lower = response.lower()
        for word in warm_words:
            if word in response_lower:
                score += 0.05

        # Check for conversational markers
        if "?" in response:
            score += 0.1  # Engaging with follow-up

        return min(score, 1.0)

    def get_stats(self) -> dict[str, Any]:
        """Get personality agent statistics."""
        return {
            "available": self.available,
            "style": self._style.value,
            "warmth_level": self._config.warmth_level,
            "humor_enabled": self._config.humor_enabled,
        }
