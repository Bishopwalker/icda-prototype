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
from difflib import get_close_matches
from typing import Any

from .models import IntentResult, QueryContext, ParsedQuery

logger = logging.getLogger(__name__)


class ParserAgent:
    """Normalizes queries and extracts structured information.

    Follows the enforcer pattern - receives only the context it needs.
    """
    __slots__ = ("_db", "_available")

    # Common state misspellings -> correct name
    STATE_TYPOS = {
        # Kansas variations
        "kanas": "kansas", "kanses": "kansas", "kanzas": "kansas", "kanss": "kansas",
        # California variations
        "californa": "california", "californai": "california", "califronia": "california",
        # Florida variations
        "flordia": "florida", "florda": "florida", "floirda": "florida",
        # Texas variations
        "texs": "texas", "texsa": "texas", "teaxs": "texas",
        # Arizona variations
        "arizon": "arizona", "arizonia": "arizona", "arizonza": "arizona",
        "argintina": "arizona",  # Common confusion
        # New York variations
        "newyork": "new york", "new yor": "new york", "newy ork": "new york",
        # Pennsylvania variations
        "pennsylvnia": "pennsylvania", "pensilvania": "pennsylvania", "pensylvania": "pennsylvania",
        # Other common typos
        "gorgia": "georgia", "virgina": "virginia", "michagan": "michigan",
        "colordo": "colorado", "nevda": "nevada", "washingon": "washington",
        "illnois": "illinois", "ohoi": "ohio", "noth carolina": "north carolina",
    }

    # State name to code mapping (full names only - no abbreviations that conflict with words)
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
        "district of columbia": "DC", "d.c.": "DC",
        # Common variations that don't conflict with English words
        "cali": "CA", "vegas": "NV",
    }

    # State codes that are also common English words - require special context
    AMBIGUOUS_STATE_CODES = {"IN", "OR", "ME", "OK", "HI", "OH", "LA", "PA", "MA", "DC"}

    # All valid state codes
    VALID_STATE_CODES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "PR", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
    }

    # All state names for fuzzy matching
    ALL_STATE_NAMES = [
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
        "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
        "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
        "maine", "maryland", "massachusetts", "michigan", "minnesota",
        "mississippi", "missouri", "montana", "nebraska", "nevada",
        "new hampshire", "new jersey", "new mexico", "new york",
        "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
        "pennsylvania", "puerto rico", "rhode island", "south carolina",
        "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
        "washington", "west virginia", "wisconsin", "wyoming",
        "district of columbia",
    ]

    # Move count interpretations
    MOVE_PATTERNS = {
        r"high\s+movers?": 5,
        r"frequent\s+movers?": 3,
        r"multiple\s+moves?": 2,
        r"moved\s+(\d+)\+?\s+times?": None,  # Extract number
        r"(\d+)\+?\s+moves?": None,  # Extract number
        r"moved\s+(?:at\s+least\s+)?(\d+)": None,  # Extract number
    }

    def _correct_state_typos(self, text: str, notes: list[str]) -> str:
        """Correct common state name misspellings.

        Args:
            text: Text to check for typos.
            notes: List to append resolution notes.

        Returns:
            Text with typos corrected.
        """
        text_lower = text.lower()
        for typo, correct in self.STATE_TYPOS.items():
            if typo in text_lower:
                # Replace the typo with the correct spelling
                text = re.sub(
                    rf"\b{re.escape(typo)}\b",
                    correct,
                    text,
                    flags=re.IGNORECASE
                )
                notes.append(f"Corrected typo: '{typo}' → '{correct}'")
        return text

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

    def _fuzzy_match_state(self, word: str, notes: list[str]) -> str | None:
        """Try to fuzzy match a word to a state name.

        Args:
            word: Word to match.
            notes: Resolution notes to append to.

        Returns:
            State code if matched, None otherwise.
        """
        word_lower = word.lower().strip()

        # Skip very short words or common English words
        if len(word_lower) < 4:
            return None

        # Try exact match first
        if word_lower in self.STATE_NAMES:
            return self.STATE_NAMES[word_lower]

        # Try fuzzy matching with high threshold (0.8 = must be very similar)
        matches = get_close_matches(word_lower, self.ALL_STATE_NAMES, n=1, cutoff=0.8)
        if matches:
            matched_name = matches[0]
            code = self.STATE_NAMES[matched_name]
            notes.append(f"Fuzzy matched '{word}' → {matched_name} ({code})")
            return code

        return None

    def _is_likely_state_code_context(self, query: str, code: str, position: int) -> bool:
        """Check if a 2-letter code is likely meant as a state code based on context.

        Args:
            query: The full query.
            code: The 2-letter code found.
            position: Position of the code in the query.

        Returns:
            True if likely a state code, False if likely a common word.
        """
        # Check for patterns that indicate it's a state code:
        # - Preceded by city name pattern: "City, ST" or "City ST"
        # - Followed by ZIP code
        # - Part of address-like patterns

        # Look for city-state patterns (e.g., "New York, NY" or "Denver CO")
        before = query[:position].strip()
        after = query[position + 2:].strip()

        # Check for comma before (strong indicator of city, state)
        if before.endswith(","):
            return True

        # Check for ZIP code after
        if re.match(r"^\s*\d{5}", after):
            return True

        # Check if preceded by a capitalized word (likely city name)
        # Pattern: "CityName ST" where ST is preceded by a word starting with capital
        city_pattern = re.search(r"([A-Z][a-z]+)\s*$", before)
        if city_pattern:
            potential_city = city_pattern.group(1).lower()
            # Make sure it's not a common word
            common_words = {"how", "many", "users", "are", "the", "for", "from", "with"}
            if potential_city not in common_words and potential_city not in self.STATE_NAMES:
                return True

        # For ambiguous codes, be conservative - require clear context
        return False

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

        # Correct state typos BEFORE normalizing state names
        normalized = self._correct_state_typos(normalized, notes)

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

        # Extract state codes with context-aware filtering
        # Find all 2-letter uppercase sequences with their positions
        for match in re.finditer(r"\b([A-Z]{2})\b", query):
            code = match.group(1)
            position = match.start()

            # Skip if not a valid state code
            if code not in self.VALID_STATE_CODES:
                continue

            # For ambiguous codes (IN, OR, ME, etc.), require clear context
            if code in self.AMBIGUOUS_STATE_CODES:
                if not self._is_likely_state_code_context(query, code, position):
                    print(f"[DEBUG] Skipping ambiguous state code '{code}' - not in state context")
                    continue

            if code not in entities["states"]:
                entities["states"].append(code)

        # Correct state typos before looking up state names
        corrected_query = self._correct_state_typos(query, notes)

        # Extract state names (exact match) and convert to codes
        for name, code in self.STATE_NAMES.items():
            # Use word boundary matching to avoid partial matches
            pattern = rf"\b{re.escape(name)}\b"
            if re.search(pattern, corrected_query.lower()) and code not in entities["states"]:
                entities["states"].append(code)
                notes.append(f"State: '{name}' → {code}")

        # Fuzzy match for potential misspelled state names
        # Look for capitalized words that might be misspelled states
        words = re.findall(r"\b([A-Z][a-z]+)\b", query)
        for word in words:
            # Skip if too short or already matched
            if len(word) < 4:
                continue

            # Try fuzzy matching
            fuzzy_code = self._fuzzy_match_state(word, notes)
            if fuzzy_code and fuzzy_code not in entities["states"]:
                entities["states"].append(fuzzy_code)

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

        # Correct state typos before processing
        corrected_query = self._correct_state_typos(query, notes)
        query_lower = corrected_query.lower()
        print(f"[DEBUG] ParserAgent._extract_filters: query_lower={query_lower}")

        # Extract state filter - use word boundaries to avoid partial matches
        for name, code in self.STATE_NAMES.items():
            pattern = rf"\b{re.escape(name)}\b"
            if re.search(pattern, query_lower):
                filters["state"] = code
                print(f"[DEBUG] ParserAgent._extract_filters: Found state name '{name}' -> {code}")
                break

        # Try fuzzy matching for misspelled state names if no exact match
        if "state" not in filters:
            words = re.findall(r"\b([A-Z][a-z]+)\b", query)
            for word in words:
                fuzzy_code = self._fuzzy_match_state(word, notes)
                if fuzzy_code:
                    filters["state"] = fuzzy_code
                    print(f"[DEBUG] ParserAgent._extract_filters: Fuzzy matched '{word}' -> {fuzzy_code}")
                    break

        # Check for state codes (but filter out ambiguous ones without context)
        if "state" not in filters:
            for match in re.finditer(r"\b([A-Z]{2})\b", query):
                code = match.group(1)
                position = match.start()

                if code not in self.VALID_STATE_CODES:
                    continue

                # For ambiguous codes, require clear context
                if code in self.AMBIGUOUS_STATE_CODES:
                    if not self._is_likely_state_code_context(query, code, position):
                        print(f"[DEBUG] Skipping ambiguous state code '{code}' in filters")
                        continue

                filters["state"] = code
                break

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

        # Extract customer type filter
        if any(word in query_lower for word in ["business", "company", "companies", "corporate"]):
            filters["customer_type"] = "BUSINESS"
            notes.append("Customer type: BUSINESS")
        elif any(word in query_lower for word in ["residential", "homeowner", "renter"]):
            filters["customer_type"] = "RESIDENTIAL"
            notes.append("Customer type: RESIDENTIAL")
        elif "po box" in query_lower or "pobox" in query_lower:
            filters["customer_type"] = "PO_BOX"
            notes.append("Customer type: PO_BOX")

        # Extract apartment filter
        if any(word in query_lower for word in ["apartment", "apt", "unit", "condo"]):
            filters["has_apartment"] = True
            notes.append("Filter: apartment/unit addresses only")

        print(f"[DEBUG] ParserAgent._extract_filters: FINAL filters={filters}")
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
