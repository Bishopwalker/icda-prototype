"""Parser Agent - Normalizes queries and extracts entities.

This agent processes the raw query to:
1. Normalize the query text
2. Extract entities (CRIDs, names, locations)
3. Parse filter criteria
4. Extract date ranges
5. Determine result limits and sorting
"""

import logging
import re
from typing import Any

from .models import IntentResult, QueryContext, ParsedQuery

logger = logging.getLogger(__name__)


class ParserAgent:
    """Normalizes queries and extracts structured information.

    Follows the enforcer pattern - receives only the context it needs.
    """
    __slots__ = ("_db", "_available")

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
        # Common variations
        "cali": "CA", "ny": "NY", "la": "LA", "vegas": "NV",
    }

    # Move count interpretations
    MOVE_PATTERNS = {
        r"high\s+movers?": 5,
        r"frequent\s+movers?": 3,
        r"multiple\s+moves?": 2,
        r"moved\s+(\d+)\+?\s+times?": None,  # Extract number
        r"(\d+)\+?\s+moves?": None,  # Extract number
        r"moved\s+(?:at\s+least\s+)?(\d+)": None,  # Extract number
    }

    def __init__(self, db=None):
        """Initialize ParserAgent.

        Args:
            db: Optional CustomerDB for validation.
        """
        self._db = db
        self._available = True

    @property
    def available(self) -> bool:
        """Check if agent is available."""
        return self._available

    async def parse(
        self,
        query: str,
        intent: IntentResult,
        context: QueryContext,
    ) -> ParsedQuery:
        """Parse and normalize the query.

        Args:
            query: Raw user query.
            intent: Classification from IntentAgent.
            context: Context from ContextAgent.

        Returns:
            ParsedQuery with extracted information.
        """
        resolution_notes = []

        # Normalize query
        normalized = self._normalize_query(query, resolution_notes)

        # Extract entities
        entities = self._extract_entities(query, context, resolution_notes)

        # Extract filters
        filters = self._extract_filters(query, context, resolution_notes)

        # Extract date range
        date_range = self._extract_date_range(query, resolution_notes)

        # Determine limit
        limit = self._extract_limit(query, context)

        # Determine sort preference
        sort_preference = self._extract_sort(query)

        # Check if follow-up
        is_follow_up = context.is_follow_up

        return ParsedQuery(
            original_query=query,
            normalized_query=normalized,
            entities=entities,
            filters=filters,
            date_range=date_range,
            sort_preference=sort_preference,
            limit=limit,
            is_follow_up=is_follow_up,
            resolution_notes=resolution_notes,
        )

    def _normalize_query(self, query: str, notes: list[str]) -> str:
        """Normalize the query text.

        Args:
            query: Raw query.
            notes: List to append resolution notes.

        Returns:
            Normalized query.
        """
        normalized = query.strip()

        # Expand common abbreviations
        expansions = [
            (r"\bcust\b", "customer"),
            (r"\bcusts\b", "customers"),
            (r"\binfo\b", "information"),
            (r"\bnum\b", "number"),
            (r"\baddr\b", "address"),
        ]

        for pattern, replacement in expansions:
            if re.search(pattern, normalized, re.IGNORECASE):
                normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
                notes.append(f"Expanded '{pattern}' to '{replacement}'")

        # Normalize state names to codes
        for name, code in self.STATE_NAMES.items():
            if name in normalized.lower():
                normalized = re.sub(
                    rf"\b{re.escape(name)}\b",
                    code,
                    normalized,
                    flags=re.IGNORECASE
                )
                notes.append(f"'{name}' → {code}")

        return normalized

    def _extract_entities(
        self,
        query: str,
        context: QueryContext,
        notes: list[str],
    ) -> dict[str, list[str]]:
        """Extract entities from query.

        Args:
            query: User query.
            context: Session context.
            notes: Resolution notes.

        Returns:
            Dict of entity type to list of values.
        """
        entities: dict[str, list[str]] = {
            "crids": [],
            "names": [],
            "states": [],
            "cities": [],
            "zips": [],
        }

        # Extract CRIDs
        crids = re.findall(r"CRID[-\s]?(\d+)", query, re.IGNORECASE)
        entities["crids"] = [f"CRID-{c.zfill(5)}" for c in crids]

        # Extract state codes
        state_codes = re.findall(r"\b([A-Z]{2})\b", query.upper())
        valid_states = {
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "PR", "RI", "SC",
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
        }
        entities["states"] = [s for s in state_codes if s in valid_states]

        # Extract state names and convert to codes
        for name, code in self.STATE_NAMES.items():
            if name in query.lower() and code not in entities["states"]:
                entities["states"].append(code)
                notes.append(f"State: '{name}' → {code}")

        # Extract ZIP codes
        zips = re.findall(r"\b(\d{5})\b", query)
        entities["zips"] = zips

        # Add referenced entities from context
        if context.referenced_entities:
            for entity in context.referenced_entities:
                if entity.startswith("CRID") and entity not in entities["crids"]:
                    entities["crids"].append(entity)

        # Add geographic context
        if context.geographic_context.get("state"):
            state = context.geographic_context["state"]
            if state not in entities["states"]:
                entities["states"].append(state)
                notes.append(f"State from context: {state}")

        return entities

    def _extract_filters(
        self,
        query: str,
        context: QueryContext,
        notes: list[str],
    ) -> dict[str, Any]:
        """Extract filter criteria from query.

        Args:
            query: User query.
            context: Session context.
            notes: Resolution notes.

        Returns:
            Dict of filter criteria.
        """
        filters: dict[str, Any] = {}
        query_lower = query.lower()

        # Extract state filter
        for name, code in self.STATE_NAMES.items():
            if name in query_lower:
                filters["state"] = code
                break

        # Check for state codes
        if "state" not in filters:
            state_match = re.search(r"\b([A-Z]{2})\b", query)
            if state_match:
                code = state_match.group(1)
                valid_states = {
                    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
                    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "PR", "RI", "SC",
                    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
                }
                if code in valid_states:
                    filters["state"] = code

        # Use context state if not in query
        if "state" not in filters and context.geographic_context.get("state"):
            filters["state"] = context.geographic_context["state"]
            notes.append(f"Using state from context: {filters['state']}")

        # Extract move count filter
        for pattern, default_count in self.MOVE_PATTERNS.items():
            match = re.search(pattern, query_lower)
            if match:
                if default_count is not None:
                    filters["min_move_count"] = default_count
                    notes.append(f"'{pattern}' → min_move_count: {default_count}")
                else:
                    # Extract number from match
                    num = int(match.group(1))
                    filters["min_move_count"] = num
                    notes.append(f"Extracted move count: {num}")
                break

        # Extract city filter (basic heuristic)
        city_patterns = [
            r"(?:in|from|near)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,?\s*[A-Z]{2}",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+customers?",
        ]
        for pattern in city_patterns:
            match = re.search(pattern, query)
            if match:
                city = match.group(1)
                # Exclude state names
                if city.lower() not in self.STATE_NAMES:
                    filters["city"] = city
                    break

        return filters

    def _extract_date_range(
        self,
        query: str,
        notes: list[str],
    ) -> tuple[str, str] | None:
        """Extract date range from query.

        Args:
            query: User query.
            notes: Resolution notes.

        Returns:
            Tuple of (start_date, end_date) or None.
        """
        query_lower = query.lower()

        # Look for relative date patterns
        if "last month" in query_lower:
            notes.append("Date range: last month")
            return ("last_month_start", "last_month_end")
        if "last year" in query_lower:
            notes.append("Date range: last year")
            return ("last_year_start", "last_year_end")
        if "this year" in query_lower:
            notes.append("Date range: this year")
            return ("this_year_start", "today")
        if "recently" in query_lower or "recent" in query_lower:
            notes.append("Date range: recent (last 30 days)")
            return ("30_days_ago", "today")

        # Look for specific date patterns (YYYY-MM-DD or MM/DD/YYYY)
        date_pattern = r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})"
        dates = re.findall(date_pattern, query)
        if len(dates) >= 2:
            return (dates[0], dates[1])
        if len(dates) == 1:
            return (dates[0], "today")

        return None

    def _extract_limit(self, query: str, context: QueryContext) -> int:
        """Extract result limit from query.

        Args:
            query: User query.
            context: Session context.

        Returns:
            Result limit.
        """
        # Check for explicit limit
        limit_patterns = [
            r"(?:top|first|show|give\s+me)\s+(\d+)",
            r"(\d+)\s+(?:customers?|results?|records?)",
            r"limit\s+(\d+)",
        ]

        for pattern in limit_patterns:
            match = re.search(pattern, query.lower())
            if match:
                return min(int(match.group(1)), 100)

        # Use context preference
        return context.user_preferences.get("preferred_limit", 10)

    def _extract_sort(self, query: str) -> str | None:
        """Extract sort preference from query.

        Args:
            query: User query.

        Returns:
            Sort field or None.
        """
        query_lower = query.lower()

        if "most moves" in query_lower or "highest movers" in query_lower:
            return "move_count_desc"
        if "least moves" in query_lower or "fewest moves" in query_lower:
            return "move_count_asc"
        if "recent" in query_lower or "newest" in query_lower:
            return "created_date_desc"
        if "oldest" in query_lower:
            return "created_date_asc"
        if "alphabetical" in query_lower or "by name" in query_lower:
            return "name_asc"

        return None
