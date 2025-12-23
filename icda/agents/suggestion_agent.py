"""Suggestion Agent - Smart suggestions for query improvements.

Generates intelligent suggestions for:
- Typo corrections
- Query refinements
- Follow-up queries
- Empty result alternatives
- Disambiguation
"""

import logging
import re
from typing import Any

from .models import (
    Suggestion,
    SuggestionContext,
    SuggestionType,
    IntentResult,
    ParsedQuery,
    SearchResult,
    EnforcedResponse,
    ResolvedQuery,
)

logger = logging.getLogger(__name__)

# Common state typos and corrections
STATE_TYPOS = {
    "califronia": "California",
    "californa": "California",
    "calfornia": "California",
    "neveda": "Nevada",
    "nevda": "Nevada",
    "arizone": "Arizona",
    "arizonia": "Arizona",
    "texes": "Texas",
    "flordia": "Florida",
    "floridia": "Florida",
    "michagan": "Michigan",
    "michigen": "Michigan",
    "massachuesetts": "Massachusetts",
    "massachusets": "Massachusetts",
    "pennyslvania": "Pennsylvania",
    "pennsilvania": "Pennsylvania",
    "georiga": "Georgia",
    "washingon": "Washington",
    "wasington": "Washington",
    "conneticut": "Connecticut",
    "connecticuit": "Connecticut",
    "minesota": "Minnesota",
    "minnisota": "Minnesota",
    "wisconson": "Wisconsin",
    "wiscosin": "Wisconsin",
    "tennesse": "Tennessee",
    "tenessee": "Tennessee",
    "illinos": "Illinois",
    "illinios": "Illinois",
    "colorodo": "Colorado",
    "coloradoo": "Colorado",
    "oregeon": "Oregon",
    "oregan": "Oregon",
}

# State full names for suggestions
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

# Neighboring states for expansion suggestions
NEIGHBORING_STATES = {
    "NV": ["CA", "OR", "ID", "UT", "AZ"],
    "AZ": ["CA", "NV", "UT", "CO", "NM"],
    "CA": ["OR", "NV", "AZ"],
    "OR": ["WA", "CA", "NV", "ID"],
    "WA": ["OR", "ID"],
    "UT": ["NV", "AZ", "CO", "WY", "ID"],
    "CO": ["WY", "NE", "KS", "OK", "NM", "AZ", "UT"],
    "TX": ["NM", "OK", "AR", "LA"],
    "FL": ["GA", "AL"],
    "NY": ["PA", "NJ", "CT", "MA", "VT"],
}

# Follow-up prompts based on result context
FOLLOW_UP_TEMPLATES = {
    "address": "Show me their full addresses",
    "details": "Tell me more about {name}",
    "similar": "Find similar customers",
    "same_state": "Who else is in {state}?",
    "high_movers": "Any high movers in the list?",
    "filter_type": "Filter by customer type",
}


class SuggestionAgent:
    """Agent for generating smart query suggestions.

    Analyzes queries and results to provide helpful
    suggestions for improvements and follow-ups.
    """

    __slots__ = ("_max_suggestions", "_confidence_threshold")

    MAX_SUGGESTIONS = 3
    CONFIDENCE_THRESHOLD = 0.5

    def __init__(
        self,
        max_suggestions: int = MAX_SUGGESTIONS,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ):
        """Initialize SuggestionAgent.

        Args:
            max_suggestions: Maximum suggestions to return.
            confidence_threshold: Minimum confidence for suggestions.
        """
        self._max_suggestions = max_suggestions
        self._confidence_threshold = confidence_threshold

    @property
    def available(self) -> bool:
        """Always available."""
        return True

    async def suggest(
        self,
        query: str,
        parsed: ParsedQuery,
        search_result: SearchResult,
        intent: IntentResult,
        resolved: ResolvedQuery | None = None,
    ) -> SuggestionContext:
        """Generate suggestions based on query and results.

        Args:
            query: Original query.
            parsed: Parsed query.
            search_result: Search results.
            intent: Intent classification.
            resolved: Resolved query info.

        Returns:
            SuggestionContext with suggestions.
        """
        suggestions = []

        # 1. Check for typos
        typo_suggestions = self._detect_typos(query, parsed)
        suggestions.extend(typo_suggestions)

        # 2. Handle empty results
        if search_result.total_matches == 0:
            empty_suggestions = self._handle_empty_results(
                query, parsed, search_result, resolved
            )
            suggestions.extend(empty_suggestions)

        # 3. Handle state unavailable
        if search_result.state_not_available:
            state_suggestions = self._handle_state_unavailable(search_result)
            suggestions.extend(state_suggestions)

        # 4. Generate follow-up suggestions for successful results
        if search_result.total_matches > 0:
            follow_ups = self._generate_follow_ups(
                query, search_result, intent
            )
            suggestions.extend(follow_ups)

        # 5. Generate refinement suggestions for large result sets
        if search_result.total_matches > 50:
            refinements = self._generate_refinements(query, parsed, search_result)
            suggestions.extend(refinements)

        # Filter by confidence and limit
        suggestions = [
            s for s in suggestions
            if s.confidence >= self._confidence_threshold
        ]
        suggestions = sorted(
            suggestions, key=lambda s: s.confidence, reverse=True
        )[:self._max_suggestions]

        # Generate follow-up prompts
        follow_up_prompts = self._generate_follow_up_prompts(
            search_result, parsed
        )

        # Pick primary suggestion
        primary = suggestions[0] if suggestions else None

        # Calculate overall confidence
        overall_confidence = (
            sum(s.confidence for s in suggestions) / len(suggestions)
            if suggestions else 0.0
        )

        return SuggestionContext(
            suggestions=suggestions,
            primary_suggestion=primary,
            follow_up_prompts=follow_up_prompts,
            suggestion_confidence=overall_confidence,
        )

    def _detect_typos(
        self,
        query: str,
        parsed: ParsedQuery,
    ) -> list[Suggestion]:
        """Detect potential typos in query."""
        suggestions = []
        query_lower = query.lower()

        # Check for state typos
        for typo, correct in STATE_TYPOS.items():
            if typo in query_lower:
                suggestions.append(Suggestion(
                    suggestion_type=SuggestionType.TYPO_FIX,
                    original=typo,
                    suggested=correct,
                    reason=f"Did you mean '{correct}'?",
                    confidence=0.9,
                    action_query=query_lower.replace(typo, correct.lower()),
                ))

        # Check resolution notes for corrections already made
        for note in parsed.resolution_notes:
            if "corrected typo" in note.lower():
                # Already corrected, high confidence
                pass

        return suggestions

    def _handle_empty_results(
        self,
        query: str,
        parsed: ParsedQuery,
        search_result: SearchResult,
        resolved: ResolvedQuery | None,
    ) -> list[Suggestion]:
        """Generate suggestions for empty results."""
        suggestions = []

        # Suggest removing filters
        if parsed.filters:
            filter_names = list(parsed.filters.keys())
            suggestions.append(Suggestion(
                suggestion_type=SuggestionType.QUERY_REFINEMENT,
                original=query,
                suggested=f"Try without the {filter_names[0]} filter",
                reason="Removing filters may find more results",
                confidence=0.7,
            ))

        # Suggest broader search
        if parsed.entities.get("cities"):
            city = parsed.entities["cities"][0]
            state = parsed.filters.get("state", "")
            if state:
                suggestions.append(Suggestion(
                    suggestion_type=SuggestionType.RESULT_EXPANSION,
                    original=query,
                    suggested=f"Try searching all of {STATE_NAMES.get(state, state)}",
                    reason="City search too narrow",
                    confidence=0.65,
                    action_query=f"customers in {state}",
                ))

        return suggestions

    def _handle_state_unavailable(
        self,
        search_result: SearchResult,
    ) -> list[Suggestion]:
        """Generate suggestions when state data unavailable."""
        suggestions = []
        requested = search_result.requested_state

        # Suggest neighboring states
        if requested and requested in NEIGHBORING_STATES:
            neighbors = NEIGHBORING_STATES[requested]
            available_neighbors = [
                s for s in neighbors
                if s in search_result.available_states
            ]
            if available_neighbors:
                neighbor = available_neighbors[0]
                neighbor_name = STATE_NAMES.get(neighbor, neighbor)
                suggestions.append(Suggestion(
                    suggestion_type=SuggestionType.RESULT_EXPANSION,
                    original=requested,
                    suggested=neighbor_name,
                    reason=f"Try nearby {neighbor_name} instead",
                    confidence=0.8,
                    action_query=f"customers in {neighbor}",
                ))

        # Suggest top available state
        if search_result.available_states_with_counts:
            top_states = sorted(
                search_result.available_states_with_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            if top_states:
                top_state, count = top_states[0]
                top_name = STATE_NAMES.get(top_state, top_state)
                suggestions.append(Suggestion(
                    suggestion_type=SuggestionType.RESULT_EXPANSION,
                    original=requested,
                    suggested=top_name,
                    reason=f"{top_name} has {count:,} customers",
                    confidence=0.75,
                    action_query=f"customers in {top_state}",
                ))

        return suggestions

    def _generate_follow_ups(
        self,
        query: str,
        search_result: SearchResult,
        intent: IntentResult,
    ) -> list[Suggestion]:
        """Generate follow-up suggestions for successful results."""
        suggestions = []
        results = search_result.results

        if not results:
            return suggestions

        # Suggest details for first result
        if len(results) >= 1:
            first = results[0]
            name = first.get("name", "this customer")
            suggestions.append(Suggestion(
                suggestion_type=SuggestionType.FOLLOW_UP,
                original=query,
                suggested=f"Tell me more about {name}",
                reason="Get detailed information",
                confidence=0.6,
                action_query=f"details for {first.get('crid', name)}",
            ))

        # Suggest same-state search if state was used
        if results and results[0].get("state"):
            state = results[0]["state"]
            state_name = STATE_NAMES.get(state, state)
            suggestions.append(Suggestion(
                suggestion_type=SuggestionType.FOLLOW_UP,
                original=query,
                suggested=f"Show more customers in {state_name}",
                reason="Explore the same region",
                confidence=0.55,
                action_query=f"customers in {state}",
            ))

        return suggestions

    def _generate_refinements(
        self,
        query: str,
        parsed: ParsedQuery,
        search_result: SearchResult,
    ) -> list[Suggestion]:
        """Generate refinement suggestions for large result sets."""
        suggestions = []
        total = search_result.total_matches

        # Suggest adding state filter if not present
        if "state" not in parsed.filters and total > 100:
            suggestions.append(Suggestion(
                suggestion_type=SuggestionType.FILTER_SUGGESTION,
                original=query,
                suggested="Add a state filter",
                reason=f"{total} results is a lot - narrow by state",
                confidence=0.7,
            ))

        # Suggest high movers filter
        if "min_move_count" not in parsed.filters and total > 50:
            suggestions.append(Suggestion(
                suggestion_type=SuggestionType.FILTER_SUGGESTION,
                original=query,
                suggested="Filter by high movers",
                reason="Find customers who move frequently",
                confidence=0.5,
                action_query=f"{query} high movers",
            ))

        return suggestions

    def _generate_follow_up_prompts(
        self,
        search_result: SearchResult,
        parsed: ParsedQuery,
    ) -> list[str]:
        """Generate quick follow-up prompts."""
        prompts = []

        if search_result.results:
            # Address prompt
            prompts.append("Show their addresses")

            # State-specific prompt
            if search_result.results[0].get("state"):
                state = search_result.results[0]["state"]
                state_name = STATE_NAMES.get(state, state)
                prompts.append(f"More in {state_name}")

            # Similar customers
            prompts.append("Find similar customers")

        elif search_result.available_states:
            # Suggest available states
            top_state = search_result.available_states[0]
            prompts.append(f"Try {STATE_NAMES.get(top_state, top_state)}")

        return prompts[:3]  # Max 3 prompts

    def get_stats(self) -> dict[str, Any]:
        """Get suggestion agent statistics."""
        return {
            "available": self.available,
            "max_suggestions": self._max_suggestions,
            "confidence_threshold": self._confidence_threshold,
        }
